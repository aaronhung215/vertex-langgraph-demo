# GCP Demo — Block 1 Execution Guide

**Goal**: Working GCP env + Vertex AI Gemini call + BigQuery synthetic data loaded.
**Time**: 80-110 min if GCP account + billing ready. Longer if creating GCP account fresh.
**Success criteria**: `03_vertex_hello.py` prints "BLOCK 1 COMPLETE ✅".

---

## Run order

| Step | File | Time | What |
|---|---|---|---|
| 1-2 | `00_SETUP_COMMANDS.md` | 35-50 min | GCP project, billing, APIs, CLI auth |
| 3a | `01_generate_data.py` | 5 min | Generate 10K synthetic delinquency rows |
| 3b | `02_load_bigquery.py` | 15-20 min | Create BQ dataset + load data |
| 4 | `03_vertex_hello.py` | 10-15 min | Verify Gemini SDK works → Block 1 done |

---

## One-time pip installs (run first)

```bash
pip install faker pandas google-cloud-bigquery pandas-gbq google-cloud-aiplatform --break-system-packages
```

---

## Quick start (after pip + GCP account exists)

```bash
# 1-2: follow 00_SETUP_COMMANDS.md, then make sure this is set:
export PROJECT_ID="your-project-id-from-step-1b"
export GCP_REGION="us-central1"

# 3a:
python 01_generate_data.py        # -> customer_transactions.csv

# 3b:
python 02_load_bigquery.py        # -> BQ table fintech_demo.customer_transactions

# 4:
python 03_vertex_hello.py         # -> "BLOCK 1 COMPLETE ✅"
```

---

## Troubleshooting (most common, fastest fixes)

| Symptom | Fix |
|---|---|
| `gcloud: command not found` | Install gcloud CLI (see 00_SETUP top) |
| `billing account not found` | https://console.cloud.google.com/billing → create (new users get $300 credit) |
| `PROJECT_ID env var not set` | `export PROJECT_ID="..."` in the SAME terminal you run python |
| `403 ... API not enabled` | Re-run the `gcloud services enable` block, wait 2 min |
| `DefaultCredentialsError` | Run `gcloud auth application-default login` |
| Gemini `model not found` | Script auto-tries 4 model names; if all fail, region issue — keep `us-central1` |
| `pandas-gbq` import error | It's optional; `02_load_bigquery.py` uses `load_table_from_file`, ignore |
| Quota/permission on first call | Wait 2-3 min after enabling APIs — propagation delay |

---

## If you run out of time

Partial completion is fine. Priority within Block 1:
1. **Steps 1-2 (env + auth)** — must finish, everything depends on this
2. **Step 4 (Gemini hello-world)** — proves the core JD keyword works
3. Step 3 (BigQuery) — can do at start of next session if time runs out

Minimum "Block 1 meaningfully started" = Steps 1-2 done + Gemini call works.
BigQuery load can slip to Block 2 start without breaking anything.

---

## What this sets up for next session

- Block 2: `01_generate_data.py` corpus pattern reused for the RAG fake docs
- Block 3: the BQ table here becomes the tool-calling target
- Narrative: synthetic schema mirrors NP credit-risk domain on purpose →
  demo story = resume story extension (the cross-stack comparison angle)
