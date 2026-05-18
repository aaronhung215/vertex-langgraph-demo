"""
Eval pipeline — Step 2: score the cached agent outputs with Ragas.

Metrics (all 0-1, higher is better):
    faithfulness        — every claim in the answer supported by contexts?
    answer_relevancy    — does the answer actually address the question?
    context_precision   — are the retrieved contexts ranked relevance-first?
    context_recall      — did retrieval cover what ground_truth needs?

Judge: gemini-2.5-flash (cheap, same family as the agent itself).
Embeddings: sentence-transformers/all-MiniLM-L6-v2 (same as Block 2 — no
extra API call, keeps the judge cost bounded to LLM judging only).

Run:
    export PROJECT_ID=fintech-agent-demo-2715
    export GCP_REGION=us-central1
    python 02_score_ragas.py

Output: eval/scores.csv (per-question), eval/scores_aggregate.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from datasets import Dataset
from langchain_google_vertexai import ChatVertexAI
from langchain_huggingface import HuggingFaceEmbeddings
from ragas import evaluate
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

HERE = Path(__file__).parent
RUN_OUTPUTS = HERE / "run_outputs.jsonl"
SCORES_CSV = HERE / "scores.csv"
SCORES_JSON = HERE / "scores_aggregate.json"

PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")
if not PROJECT_ID:
    raise SystemExit('Set: export PROJECT_ID="your-gcp-project"')
if not RUN_OUTPUTS.exists():
    raise SystemExit(f"Missing {RUN_OUTPUTS}. Run 01_run_agent.py first.")


def main() -> None:
    runs = [
        json.loads(line)
        for line in RUN_OUTPUTS.read_text().splitlines()
        if line.strip()
    ]
    print(f"Loaded {len(runs)} cached runs")

    # Drop runs that errored — they have no answer to score.
    scoreable = [r for r in runs if r.get("answer")]
    skipped = len(runs) - len(scoreable)
    if skipped:
        print(f"Skipping {skipped} runs with empty answer (agent error)")

    ds = Dataset.from_dict({
        "question":     [r["question"]     for r in scoreable],
        "ground_truth": [r["ground_truth"] for r in scoreable],
        "answer":       [r["answer"]       for r in scoreable],
        # Ragas requires non-empty contexts; substitute a placeholder for
        # BQ-only runs that bypassed the retriever. Context-precision/recall
        # will score those low, which is correct — there are no contexts
        # to evaluate.
        "contexts":     [r["contexts"] or ["(no context retrieved)"]
                         for r in scoreable],
    })

    print(f"Configuring judge: gemini-2.5-flash via Vertex (project={PROJECT_ID})")
    judge_llm = ChatVertexAI(
        model_name="gemini-2.5-flash",
        project=PROJECT_ID,
        location=REGION,
        temperature=0,
    )
    judge_embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
    )

    print(f"Scoring {len(scoreable)} runs against 4 Ragas metrics "
          "(~80 LLM judge calls, ~3-5 min)...")
    result = evaluate(
        dataset=ds,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ],
        llm=LangchainLLMWrapper(judge_llm),
        embeddings=LangchainEmbeddingsWrapper(judge_embeddings),
        raise_exceptions=False,  # one bad row shouldn't abort the whole run
    )

    df = result.to_pandas()
    # Re-attach the case id + expected_path so the CSV is self-explanatory
    df.insert(0, "id", [r["id"] for r in scoreable])
    df.insert(1, "expected_path", [r["expected_path"] for r in scoreable])
    df.to_csv(SCORES_CSV, index=False)
    print(f"\nPer-question scores → {SCORES_CSV}")

    # Aggregate, including per-path slices (rag_only / bq_only / both).
    metric_cols = [c for c in (
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
    ) if c in df.columns]

    overall = {m: float(df[m].mean()) for m in metric_cols}
    by_path = {}
    for path in df["expected_path"].unique():
        sub = df[df["expected_path"] == path]
        by_path[path] = {m: float(sub[m].mean()) for m in metric_cols}
        by_path[path]["n"] = int(len(sub))

    summary = {"overall": overall, "by_path": by_path,
               "n_total": len(scoreable), "n_skipped": skipped}
    SCORES_JSON.write_text(json.dumps(summary, indent=2))

    print("\nAggregate (all questions):")
    for m in metric_cols:
        print(f"  {m:20s} {overall[m]:.3f}")
    print("\nBy expected path:")
    for path, scores in by_path.items():
        n = scores.pop("n")
        line = "  ".join(f"{m}={scores[m]:.3f}" for m in metric_cols)
        print(f"  {path:10s} (n={n})  {line}")

    print(f"\nAggregate JSON → {SCORES_JSON}")
    print("Inspect per-question reasoning in scores.csv for any score < 0.7.")


if __name__ == "__main__":
    main()
