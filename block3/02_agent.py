"""
GCP Demo Block 3 — Step 2: LangGraph agent (planner + RAG + BQ tool + reflection).

State graph:

    START -> planner -> (retriever || bq_executor) -> synthesizer -> reflection -> END

- planner emits structured JSON deciding which tools to use
- retriever and bq_executor run in parallel after the plan is set
- synthesizer waits for both, builds grounded answer with citations
- reflection self-checks for ungrounded claims (transparency, no retry loop)

Re-uses the FAISS index from Block 2 and the BQ tool from Block 3 step 1.

Run:
    export PROJECT_ID=fintech-agent-demo-2715
    export GCP_REGION=us-central1
    python 02_agent.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

import faiss
import numpy as np
from google import genai
from google.genai import types as gtypes
from langgraph.graph import END, START, StateGraph
from langsmith import traceable
from sentence_transformers import SentenceTransformer

# Local import: the BQ tool from step 1 sits next to this file.
sys.path.insert(0, str(Path(__file__).parent))
from importlib import import_module  # noqa: E402

bq_tool = import_module("01_bq_tool")
delinquency_breakdown = bq_tool.delinquency_breakdown
format_as_table = bq_tool.format_as_table
ToolInputError = bq_tool.ToolInputError

PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")
MODEL = "gemini-2.5-flash"

if not PROJECT_ID:
    raise SystemExit('Set: export PROJECT_ID="your-project-id"')

# ----- Retrieval (re-uses Block 2 artifacts) -----------------------------
BLOCK2 = Path(__file__).parent.parent / "block2"
INDEX_PATH = BLOCK2 / "faiss_index.bin"
META_PATH = BLOCK2 / "doc_meta.jsonl"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_embedder: SentenceTransformer | None = None
_index: faiss.Index | None = None
_docs: list[dict] | None = None


def _ensure_retrieval_loaded():
    global _embedder, _index, _docs
    if _embedder is None:
        if not INDEX_PATH.exists() or not META_PATH.exists():
            raise SystemExit(
                f"Missing {INDEX_PATH} or {META_PATH}. "
                "Run block2/02_index_faiss.py first."
            )
        print(f"  [load] embedder + FAISS index from {BLOCK2.name}/")
        _embedder = SentenceTransformer(EMBED_MODEL)
        _index = faiss.read_index(str(INDEX_PATH))
        _docs = [
            json.loads(line)
            for line in META_PATH.read_text().splitlines()
            if line
        ]
    return _embedder, _index, _docs


def retrieve(query: str, k: int = 3) -> list[dict[str, Any]]:
    embedder, index, docs = _ensure_retrieval_loaded()
    q = embedder.encode([query], normalize_embeddings=True).astype(np.float32)
    D, I = index.search(q, k=k)
    return [
        {"id": docs[i]["id"], "title": docs[i]["title"],
         "text": docs[i]["text"], "score": float(d)}
        for d, i in zip(D[0], I[0])
    ]


# ----- LangGraph state ----------------------------------------------------

class AgentState(TypedDict, total=False):
    question: str
    plan: dict
    retrieved: list[dict]
    bq_rows: list[dict]
    bq_error: str
    draft: str
    reflection: str


# ----- LLM client (lazy) --------------------------------------------------

_client: genai.Client | None = None


def _llm() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
    return _client


@traceable(run_type="llm", name=f"gemini-2.5-flash")
def _gen(prompt: str, *, json_mode: bool = False, max_tokens: int = 600) -> str:
    """Single LLM call. Wrapped with @traceable so each call appears as its
    own span in LangSmith when LANGSMITH_TRACING=true. No-op when the env var
    is unset (traceable becomes a passthrough)."""
    cfg = gtypes.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=max_tokens,
        thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json" if json_mode else None,
    )
    resp = _llm().models.generate_content(model=MODEL, contents=prompt, config=cfg)
    return resp.text.strip()


# ----- Nodes --------------------------------------------------------------

PLANNER_PROMPT = """You route a FinTech analyst's question to the right tools.

Two tools available:
1. retrieve_docs — searches internal policy/data-dictionary/playbook docs.
   Use for: definitions, policies, processes, "what is X", "how do we do Y".
2. query_bigquery — aggregations on customer_transactions.
   Columns: customer_id, transaction_date, quarter (Q1-Q4), is_new_buyer (bool),
   merchant_segment (travel/gaming/retail), order_value_twd, is_delinquent,
   days_late, credit_limit_twd, device_type (ios/android/web).
   Use for: "show me the rate", "compare X vs Y", "which segment has...".

Both tools can be used together for analytical questions that need policy
context AND numbers.

Output STRICT JSON only:
{
  "use_rag": bool,
  "use_bq": bool,
  "bq_args": {"group_by": [...], "filters": {...}} or null,
  "reasoning": "one short sentence"
}

bq_args.group_by must be subset of ["quarter","is_new_buyer","merchant_segment","device_type"]
bq_args.filters keys must be from the same set.

QUESTION: {question}
"""


def planner(state: AgentState) -> dict:
    raw = _gen(PLANNER_PROMPT.replace("{question}", state["question"]),
               json_mode=True, max_tokens=300)
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try both tools, no bq_args
        plan = {"use_rag": True, "use_bq": False, "bq_args": None,
                "reasoning": "planner JSON parse failed; fell back to RAG-only"}
    return {"plan": plan}


def retriever(state: AgentState) -> dict:
    plan = state.get("plan", {})
    if not plan.get("use_rag"):
        return {}
    docs = retrieve(state["question"], k=3)
    return {"retrieved": docs}


def bq_executor(state: AgentState) -> dict:
    plan = state.get("plan", {})
    if not plan.get("use_bq"):
        return {}
    args = plan.get("bq_args") or {}
    group_by = args.get("group_by") or []
    filters = args.get("filters")
    try:
        rows = delinquency_breakdown(group_by=group_by, filters=filters)
        return {"bq_rows": rows}
    except (ToolInputError, Exception) as e:  # noqa: BLE001
        return {"bq_error": f"{type(e).__name__}: {e}"}


SYNTH_PROMPT = """You answer a FinTech analyst's question using ONLY the evidence below.

Rules:
- Cite policy docs inline with [doc-id]. Cite numeric claims with "(per the data table)".
- If evidence is insufficient, say so explicitly.
- Be concise (3-5 sentences typically; can be longer for analytical questions).

DOCS:
{docs}

DATA (BigQuery aggregate):
{data}

QUESTION: {question}

ANSWER:"""


def synthesizer(state: AgentState) -> dict:
    docs_block = "(none retrieved)"
    if state.get("retrieved"):
        docs_block = "\n\n".join(
            f"[{d['id']}] {d['title']}\n{d['text']}" for d in state["retrieved"]
        )
    data_block = "(no query run)"
    if state.get("bq_error"):
        data_block = f"(tool error: {state['bq_error']})"
    elif state.get("bq_rows"):
        data_block = format_as_table(state["bq_rows"])
    prompt = (
        SYNTH_PROMPT
        .replace("{docs}", docs_block)
        .replace("{data}", data_block)
        .replace("{question}", state["question"])
    )
    return {"draft": _gen(prompt, max_tokens=800)}


REFLECT_PROMPT = """Review the draft answer below. Check:
1. Is every factual claim supported by the evidence shown?
2. Are doc citations [doc-id] present where needed?
3. Are numeric claims attributed to the data table?

EVIDENCE (docs + data):
{evidence}

DRAFT:
{draft}

If all OK, output exactly: OK
Otherwise output ONE short sentence describing the most important fix.
"""


def reflection(state: AgentState) -> dict:
    evidence_parts = []
    if state.get("retrieved"):
        evidence_parts.append("DOCS:\n" + "\n".join(
            f"[{d['id']}] {d['title']}" for d in state["retrieved"]
        ))
    if state.get("bq_rows"):
        evidence_parts.append("DATA:\n" + format_as_table(state["bq_rows"]))
    evidence = "\n\n".join(evidence_parts) or "(none)"
    prompt = (
        REFLECT_PROMPT
        .replace("{evidence}", evidence)
        .replace("{draft}", state.get("draft", ""))
    )
    return {"reflection": _gen(prompt, max_tokens=200)}


# ----- Graph build --------------------------------------------------------

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("planner", planner)
    g.add_node("retriever", retriever)
    g.add_node("bq_executor", bq_executor)
    g.add_node("synthesizer", synthesizer)
    g.add_node("reflection", reflection)
    g.add_edge(START, "planner")
    # Fan out: planner -> retriever AND bq_executor (parallel)
    g.add_edge("planner", "retriever")
    g.add_edge("planner", "bq_executor")
    # Fan in: both feed synthesizer (LangGraph waits for both)
    g.add_edge("retriever", "synthesizer")
    g.add_edge("bq_executor", "synthesizer")
    g.add_edge("synthesizer", "reflection")
    g.add_edge("reflection", END)
    return g.compile()


# ----- Demo runner --------------------------------------------------------

DEMO_QUERIES = [
    # RAG-only
    "What is our target unpaid rate, and how is is_delinquent defined?",
    # BQ-only
    "Show me delinquency rate broken down by quarter.",
    # Both — the centerpiece narrative
    "Q3 new-buyer delinquency feels high. What does the data actually show, "
    "and what's our standard SOP for investigating a quarterly spike?",
]


def print_run(i: int, question: str, final_state: dict) -> None:
    sep = "=" * 78
    print(f"\n{sep}\nQ{i}: {question}\n{sep}")
    plan = final_state.get("plan", {})
    print(f"PLAN  use_rag={plan.get('use_rag')}  use_bq={plan.get('use_bq')}"
          f"  bq_args={plan.get('bq_args')}")
    print(f"      reasoning: {plan.get('reasoning')}")
    if final_state.get("retrieved"):
        print("RETRIEVED:")
        for d in final_state["retrieved"]:
            print(f"  score={d['score']:.3f}  [{d['id']}] {d['title']}")
    if final_state.get("bq_rows"):
        print("BQ ROWS:")
        print(format_as_table(final_state["bq_rows"]))
    if final_state.get("bq_error"):
        print(f"BQ ERROR: {final_state['bq_error']}")
    print(f"\nDRAFT:\n  {final_state.get('draft','').strip()}")
    print(f"\nREFLECTION: {final_state.get('reflection','').strip()}")


def main() -> None:
    graph = build_graph()
    print("Compiled LangGraph: planner -> (retriever || bq_executor) -> synthesizer -> reflection")
    for i, q in enumerate(DEMO_QUERIES, 1):
        final = graph.invoke({"question": q})
        print_run(i, q, final)
    print("\n" + "=" * 78)
    print("BLOCK 3 COMPLETE ✅")
    print(f"  Agent: LangGraph state machine with 5 nodes (1 planner, 2 parallel tools, "
          "1 synth, 1 reflection)")
    print(f"  LLM:   {MODEL} via google-genai")
    print(f"  Tools: FAISS RAG (from Block 2) + parameterised BigQuery aggregator")
    print("Next: Block 4 (Go MCP tool ~100 lines)")


if __name__ == "__main__":
    main()
