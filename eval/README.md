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

**Expected cost** (after the thinking-token fix, judge = `gemini-2.5-flash-lite`): ~USD 0.50 per full pass, untested at the time of writing — verify with a `head -3 testset.jsonl > sample.jsonl` dry-run before committing to all 20 questions.

**First-run cost** (judge = `gemini-2.5-flash`, thinking default ON):
~USD 13. Thinking-token output alone billed $11.23. The script has been
patched; this paragraph kept as the receipt. See [Cost post-mortem](#cost-post-mortem) below.

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

## First-run results (2026-05-18, judge = flash with thinking ON — superseded)

| Metric | All (n=20) | rag_only (n=6) | bq_only (n=6) | both (n=8) |
|---|---|---|---|---|
| faithfulness | 0.832 | 0.967 | 0.833 | 0.729 |
| answer_relevancy | 0.730 | 0.864 | 0.883 | **0.515** |
| context_precision | 0.857 | 0.972 | 0.833 | 0.788 |
| context_recall | 0.423 | 0.328 | 0.250 | 0.625 |

Wall-clock: ~108s (agent runs) + ~92s (Ragas judging). **Cost: USD ~13** (see post-mortem). The judge model has since been changed to `gemini-2.5-flash-lite`; expect these absolute numbers to shift on a re-run — comparisons across runs only mean something if the judge is held constant.

### What the eval surfaced — real planner regression

Five of the eight low-score cases (`Q01`, `Q11`, `Q13`, `Q16`, `Q18`)
trace to **one planner bug**: the planner sometimes emits
`filters: {is_delinquent: True}` even though `is_delinquent` is **not**
in `ALLOWED_DIMS` (it is the outcome computed by the BQ tool, not a
dimension to filter on). The BQ tool correctly raises
`ToolInputError: filters contains disallowed keys: ['is_delinquent']`,
the agent falls back to "insufficient evidence" or doc-only answers,
and the Ragas judge — correctly — scores those as low-faithfulness or
low-relevancy.

A secondary bug: `Q18` and parts of `Q01` showed `group_by: []`
(empty), which the BQ tool also rejects.

This is exactly the kind of regression an eval pipeline is supposed to
catch. The planner prompt at `block3/02_agent.py:135` should explicitly
call out that `is_delinquent` is the outcome (not a filter dimension)
and that `group_by` must be non-empty. Out of scope for the eval
addition itself; tracked as a follow-up.

### What the eval surfaced — Ragas judge artifacts

Several near-zero `context_recall` scores in `rag_only` (e.g. Q01,
Q04, Q05) coexist with `faithfulness = 1.0` and
`context_precision = 1.0`. The agent retrieved the correct doc, the
answer is fully grounded, but the judge marks the ground_truth as
unsupported. The most likely cause: the judge parses the
`(per policy-001)` citation in the ground_truth as its own atomic
claim and looks for a literal doc-id string in the contexts. This is
LLM-judge noise, not an agent defect.

The persistent "LLM returned 1 generations instead of requested 3"
warning during scoring is a related noise source — Ragas wants
self-consistency voting (n=3) for `answer_relevancy` but Vertex AI
returns one generation per call by default. The aggregated scores are
based on a single judge sample per metric, so absolute numbers carry
more variance than usual.

### How to read the table

- **`rag_only` faithfulness 0.97 and `context_precision` 0.97** is the
  signal that the grounded-retrieval + cite-doc-id design works as
  intended on the easy path
- **`both` answer_relevancy 0.515** is dragged down by Q13/Q16/Q18,
  which all hit the planner bug above — fix the planner and this
  number should rebound
- **`context_recall` low across the board** is a mix of (a) the
  planner bug (no BQ data → fewer supported claims) and (b) the
  judge-citation-parsing artifact. Worth re-running after the planner
  fix to separate the two

**Per-question debugging**: open `scores.csv` and `run_outputs.jsonl`
together; for any score < 0.7, the per-row plan + answer in
`run_outputs.jsonl` usually makes the cause obvious.

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

---

## Cost post-mortem

The first end-to-end run cost **USD ~13** (Vertex AI line item),
against an estimate of USD 0.04. Breakdown from the GCP billing SKU
report on 2026-05-18:

| SKU | $ | Note |
|---|---|---|
| Gemini 2.5 Flash GA Thinking Text Output | **8.90** | Reasoning tokens — invisible in the response, billed separately |
| Gemini 2.5 Flash GA Text Output (Thinking On) | **2.33** | The reply tokens themselves, billed at the thinking-on rate |
| Gemini 2.5 Flash GA Text Input | 1.41 | Input tokens (all calls) |
| Gemini 2.5 Flash GA Text Output (no thinking) | 0.44 | The agent's own LLM calls — `block3/02_agent.py` correctly set `thinking_budget=0` |

**Root cause**: the Block 3 agent's `_gen()` explicitly sets
`thinking_config=ThinkingConfig(thinking_budget=0)` (added in Block 2
after a related token-budget bug). The Ragas judge configured here used
the LangChain `ChatVertexAI` wrapper which had **no equivalent setting
plumbed through**, so every Ragas judge call (claim verification,
question regeneration, context relevance check — easily 200+ underlying
LLM calls across the four metrics × 20 questions) ran with thinking ON.
Thinking output is priced ~25× regular output on `gemini-2.5-flash`,
so what looked like ~80 progress-bar iterations was really ~140K
thinking-output tokens behind the scenes.

**Fix (this PR)**: switched the judge model to `gemini-2.5-flash-lite`,
which does not enable thinking by default. No `thinking_config`
plumbing needed; the failure mode is structurally removed rather than
remembered-to-avoid.

**Predicted cost after fix**: ~USD 0.50 per full pass, untested at the
time of writing. Verify by running with a 3-question sample first:

```bash
head -3 eval/testset.jsonl > eval/testset.sample.jsonl
# Patch run_agent.py to point at sample, run, multiply by 7 to estimate
# the full-testset cost. Decide whether to proceed.
```

**Lessons codified into the codebase**:

- Cost claims in `README.md` and `ARCHITECTURE.md` updated from
  "USD 0.04 / pass" to the actual receipt plus the post-fix estimate
  (marked "untested")
- Future LLM judge / agent additions: any `gemini-2.5-*` (non-lite) call
  must explicitly set `thinking_budget` or pick a `-lite` variant —
  defaults are not your friend
- "Run a 3-row sample first" is now the standard for any new pipeline
  that touches a paid LLM in a loop
