# GCP Demo — Block 2 Execution Guide

**Goal**: Working RAG baseline — synthetic FinTech corpus + sentence-transformers + FAISS + Gemini grounding.
**Time**: 60-90 min (first run slower due to model download).
**Success criteria**: `03_rag_gemini.py` answers 5 test queries with cited doc ids and prints "BLOCK 2 COMPLETE ✅".

---

## Run order

| Step | File | Time | What |
|---|---|---|---|
| 1 | `01_build_corpus.py` | 1 min | Write 15 NP-domain credit-risk docs to corpus.jsonl |
| 2 | `02_index_faiss.py` | 5-15 min | Embed + build FAISS index (downloads `all-MiniLM-L6-v2` first run) |
| 3 | `03_rag_gemini.py` | 5-10 min | RAG grounded answer for 5 fixed test queries |

---

## One-time pip installs

```bash
pip install sentence-transformers faiss-cpu --break-system-packages
```

(`google-genai` already installed as a dep from Block 1.)

---

## Quick start

```bash
export PROJECT_ID="fintech-agent-demo-2715"
export GCP_REGION="us-central1"

python 01_build_corpus.py      # -> corpus.jsonl (15 docs)
python 02_index_faiss.py       # -> faiss_index.bin + doc_meta.jsonl
python 03_rag_gemini.py        # -> 5 grounded Q&A + "BLOCK 2 COMPLETE ✅"
```

---

## Design choices

| Choice | Why |
|---|---|
| **Local FAISS** over Vertex AI Vector Search | Faster setup; the JD keyword is "RAG", not specifically Vector Search. Vector Search is the production-grade architectural alternative — mentioned here, not implemented |
| **`all-MiniLM-L6-v2`** (384-dim) | Small (~80MB), CPU-fast, sufficient for 15-doc corpus. For 1M+ docs production scale, swap to `text-embedding-004` via Vertex AI |
| **`IndexFlatIP` + normalized vectors** | Exact cosine on a small corpus. Avoids HNSW/IVF tuning that doesn't matter at this scale |
| **`google-genai` SDK** over `vertexai.generative_models` | The `vertexai` SDK is deprecated 2026-06-24 (~5 weeks out). `google-genai` is the supported path forward and works the same way |
| **15 docs, NP-domain** | Same domain as Block 1's BigQuery schema → one coherent demo story (Block 3 will chain RAG + BQ in a single LangGraph) |
| **`temperature=0.1`** | Grounding tasks should be near-deterministic; higher temp encourages hallucination away from the cited context |

---

## Architectural alternative (mention in cover letter / interview)

For production scale (1M+ chunks, multi-tenant, write-throughput):

| Local stack (this demo) | Production alternative |
|---|---|
| FAISS in-memory | Vertex AI Vector Search (managed, regional) |
| `all-MiniLM-L6-v2` local | `text-embedding-004` via Vertex embedding API |
| File-based persistence | Vector Search index + Cloud Storage |

This is the "cross-stack comparison" the cover letter promises — pick the right tool for the scale.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `corpus.jsonl not found` | Run `01_build_corpus.py` first |
| Model download stalls | First run downloads ~80MB; check network or `HF_HUB_OFFLINE` env |
| `PermissionDenied` from Gemini | Re-check Block 1 setup: billing linked, ADC done, `gcloud config get-value project` matches |
| Cited doc id missing from answer | Lower temperature, or expand `TOP_K` to 5 in `03_rag_gemini.py` |

---

## What this sets up for Block 3

- The `retrieve(query, k)` pattern in `03_rag_gemini.py` becomes a **LangGraph tool node** in Block 3.
- The grounded-prompt template is reused inside the LangGraph synthesizer.
- Block 3 adds a **BigQuery tool** (querying `fintech_demo.customer_transactions` from Block 1) so the agent can fetch real numbers in addition to policy text.
