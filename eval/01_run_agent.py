"""
Eval pipeline — Step 1: run the Block 3 agent over the 20-question testset
and persist (question, answer, contexts, retrieved_doc_ids, plan, reflection)
so the scoring step can iterate fast without re-paying for agent runs.

Run:
    export PROJECT_ID=fintech-agent-demo-2715
    export GCP_REGION=us-central1
    python 01_run_agent.py

Output: eval/run_outputs.jsonl
"""

from __future__ import annotations

import json
import os
import sys
import time
from importlib import import_module
from pathlib import Path

HERE = Path(__file__).parent
BLOCK3 = HERE.parent / "block3"
sys.path.insert(0, str(BLOCK3))

# Block 3 uses numeric filename prefixes; import_module is the workaround.
agent_mod = import_module("02_agent")
build_graph = agent_mod.build_graph
format_as_table = agent_mod.format_as_table

PROJECT_ID = os.environ.get("PROJECT_ID")
if not PROJECT_ID:
    raise SystemExit('Set: export PROJECT_ID="your-gcp-project"')

TESTSET = HERE / "testset.jsonl"
OUT = HERE / "run_outputs.jsonl"


def main() -> None:
    cases = [
        json.loads(line)
        for line in TESTSET.read_text().splitlines()
        if line.strip()
    ]
    print(f"Loaded {len(cases)} cases from {TESTSET.name}")

    graph = build_graph()
    print("Compiled Block 3 LangGraph")

    outputs: list[dict] = []
    t0 = time.time()
    for i, case in enumerate(cases, 1):
        qid = case["id"]
        question = case["question"]
        print(f"  [{i:>2}/{len(cases)}] {qid}: {question[:70]}...")
        try:
            final = graph.invoke({"question": question})
        except Exception as e:  # noqa: BLE001 — surface but don't abort
            print(f"    ! agent error: {type(e).__name__}: {e}")
            outputs.append({**case, "answer": "", "contexts": [],
                            "retrieved_doc_ids": [], "plan": None,
                            "reflection": "", "error": str(e)})
            continue

        # Build contexts list for Ragas. For RAG-only and "both" questions,
        # contexts = retrieved doc texts. For BQ-only / "both", append the
        # formatted BQ table as a synthetic context entry so faithfulness can
        # check numeric claims against it.
        contexts: list[str] = [d["text"] for d in final.get("retrieved", [])]
        if final.get("bq_rows"):
            contexts.append("BQ_AGGREGATE:\n" + format_as_table(final["bq_rows"]))

        outputs.append({
            "id": qid,
            "expected_path": case.get("expected_path"),
            "question": question,
            "ground_truth": case["ground_truth"],
            "expected_doc_ids": case.get("expected_doc_ids", []),
            "answer": final.get("draft", "").strip(),
            "contexts": contexts,
            "retrieved_doc_ids": [d["id"] for d in final.get("retrieved", [])],
            "plan": final.get("plan"),
            "reflection": final.get("reflection", "").strip(),
        })

    elapsed = time.time() - t0
    with OUT.open("w") as f:
        for o in outputs:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    print(f"\nWrote {len(outputs)} runs to {OUT}")
    print(f"Total wall-clock: {elapsed:.1f}s ({elapsed/len(outputs):.1f}s per query)")
    print("Next: python 02_score_ragas.py")


if __name__ == "__main__":
    main()
