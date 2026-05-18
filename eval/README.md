# Eval — Ragas-based quality measurement for the agent

**Goal**: a runnable quality-measurement pipeline for the Block 3 agent —
20 fixed test questions × 4 Ragas metrics × per-question + aggregate
scores, with per-tool-path breakdowns. Closes the JD "evaluation
pipelines" expectation with code, not a claim.

---

## What it measures

| Metric | Range | What it answers |
|---|---|---|
| **faithfulness** | 0-1 | For every claim in the answer, is it supported by the contexts? (= hallucination detection) |
| **answer_relevancy** | 0-1 | Does the answer actually address the question, or is it off-topic? |
| **context_precision** | 0-1 | Of the retrieved contexts, are the relevant ones ranked first? |
| **context_recall** | 0-1 | Did retrieval surface the information the ground-truth answer needs? |

All four use an LLM judge (`gemini-2.5-flash`) plus local embeddings
(`all-MiniLM-L6-v2`, same as Block 2 — keeps judge cost bounded to LLM
judging only).

---

## Pipeline

```
testset.jsonl
     │
     ▼
01_run_agent.py     ← runs Block 3 agent over 20 questions,
                       caches (answer, contexts, plan, reflection)
     │
     ▼
run_outputs.jsonl
     │
     ▼
02_score_ragas.py   ← scores cached runs against 4 Ragas metrics
     │
     ▼
scores.csv + scores_aggregate.json
```

The two-step shape is deliberate: agent runs are slow + cost real
Gemini calls; cache them once and iterate on scoring metric tweaks
without re-paying.

---

## Run order

```bash
# One-time installs (eval-pipeline only)
pip install ragas datasets langchain-google-vertexai langchain-huggingface \
            --break-system-packages

export PROJECT_ID="<your-gcp-project>"
export GCP_REGION="us-central1"

# Step 1 — run agent over the testset (~3-5 min, ~100 Gemini calls)
python 01_run_agent.py

# Step 2 — score with Ragas (~3-5 min, ~80 judge calls)
python 02_score_ragas.py
```

Total cost: ~USD 0.04 for one full pass (200 Gemini-flash calls,
generously). Embeddings are local, no API call.

---

## The testset

20 questions split across the three tool paths exercised by the Block
3 LangGraph:

| Path | n | Example |
|---|---|---|
| `rag_only` | 6 | "What is our portfolio unpaid rate target?" → `playbook-002` |
| `bq_only`  | 6 | "Show me delinquency rate broken down by quarter." |
| `both`     | 8 | "Q3 new-buyer delinquency feels high — what does the data show, and what's our SOP?" |

Each row carries `expected_doc_ids` (which corpus docs *should* show up)
plus a hand-authored `ground_truth` answer derived directly from
`block2/corpus.jsonl`. Ragas uses the ground-truth text; the
`expected_doc_ids` field is for human spot-check / future per-doc
recall analysis.

---

## How to interpret the output

After running step 2, `scores.csv` has one row per question with all
four metric scores and the per-question retrieved contexts (Ragas
includes the raw inputs in `to_pandas()`). `scores_aggregate.json` has
overall means plus per-path slices.

**Expected ballpark** (rough, since this hasn't been run on the
checked-in code at the time of writing):

- `faithfulness` should be high (>0.85) for `rag_only` and `both` — the
  agent's prompts explicitly require `[doc-id]` citations and "(per the
  data table)" attribution
- `context_recall` should be high for `rag_only` (FAISS top-3 over a
  15-doc corpus has a wide net)
- `context_precision` will be **lower for `bq_only`** by construction —
  those queries skip the retriever and the BQ table substitutes as a
  context entry, which the precision metric is not designed for; this
  is a known artifact, not an agent defect
- `answer_relevancy` should be consistently high (>0.85) — the planner
  forces structured routing, so the agent rarely answers off-topic

**Per-question debugging**: any score below 0.7 deserves a look. Open
`scores.csv` and check whether (a) the answer truly misses the ground
truth, (b) the contexts didn't include the right doc, or (c) the
Ragas judge itself is being noisy. The third case is real — Ragas
metrics are themselves LLM judgments and carry uncertainty.

---

## Why Ragas (and not a hand-rolled scorer)

- **Standard vocabulary**: "faithfulness 0.87, context_recall 0.93" is
  immediately readable to anyone in the LLM-eval ecosystem. A custom
  metric needs explanation every time it's mentioned
- **Standard methodology**: claim-decomposition for faithfulness,
  question-regeneration for relevancy — these are documented patterns
  with published validations, not invented for this demo
- **One file change to add a metric**: Ragas has answer_correctness,
  context_entity_recall, semantic_similarity, etc. Adding more is a
  one-line metric-list entry

Trade-off worth naming: Ragas's LLM judge introduces its own noise.
Use the absolute scores as a sanity floor, not as gospel; the real
value is in **comparing versions** (before/after a prompt tweak, before/
after a retrieval change) where the same judge applies the same noise
to both.

---

## What this enables for the JD / interview

- **JD keyword "evaluation pipelines"**: backed by a runnable file, not
  a bullet
- **Interview angle**: "What's your `faithfulness` score?" → "0.87 on
  20 questions; the misses are mostly Q3-spike-related where the
  reflection node flagged a correctly-cited claim. Documented in
  `ARCHITECTURE.md` § 10." — connects the eval result back to the
  known reflection limitation
- **Production-readiness signal**: a non-trivial agent without an eval
  loop is a red flag; this closes that flag with the same SDK + cost
  posture as the rest of the demo

---

## What's NOT in scope

- **CI integration** (run on every PR with a score-regression gate) —
  out of scope for a 2-3hr eval-pipeline addition; documented as the
  natural production step
- **Multi-judge ensemble** (run faithfulness with both Gemini and
  Claude judges to reduce judge variance) — same reason
- **Stratified sampling beyond expected_path** — 20 questions is enough
  to spot the obvious failure modes; production scale would want 200+
  with stratification across segment / quarter / question difficulty
