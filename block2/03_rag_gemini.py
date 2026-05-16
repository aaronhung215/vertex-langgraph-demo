"""
GCP Demo Block 2 — Step 3: RAG grounding with Gemini.

Loads the FAISS index from step 2, retrieves top-k chunks per query,
builds a grounded prompt, and calls Gemini via the google-genai SDK
(vertexai.generative_models is deprecated 2026-06-24 — see session log).

Runs 5 fixed test queries spanning policy, data-dictionary, and playbook
docs so retrieval quality is observable at a glance.

Run:
    export PROJECT_ID=fintech-agent-demo-2715
    export GCP_REGION=us-central1
    python 03_rag_gemini.py
"""

import json
import os
from pathlib import Path

import faiss
import numpy as np
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer

PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")
MODEL = "gemini-2.5-flash"
TOP_K = 3

if not PROJECT_ID:
    raise SystemExit('Set: export PROJECT_ID="your-project-id"')

HERE = Path(__file__).parent
INDEX_PATH = HERE / "faiss_index.bin"
META_PATH = HERE / "doc_meta.jsonl"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_artifacts():
    if not INDEX_PATH.exists() or not META_PATH.exists():
        raise SystemExit(
            "Missing FAISS index or doc_meta.jsonl. Run 02_index_faiss.py first."
        )
    index = faiss.read_index(str(INDEX_PATH))
    docs = [json.loads(line) for line in META_PATH.read_text().splitlines() if line]
    return index, docs


def retrieve(query: str, index, docs, embedder, k: int = TOP_K):
    q = embedder.encode([query], normalize_embeddings=True).astype(np.float32)
    D, I = index.search(q, k=k)
    return [(docs[i], float(d)) for d, i in zip(D[0], I[0])]


def build_prompt(query: str, retrieved):
    chunks = "\n\n".join(
        f"[{d['id']}] {d['title']}\n{d['text']}" for d, _ in retrieved
    )
    return (
        "You are a FinTech risk analyst assistant. Answer the user's question "
        "using ONLY the context below. Cite the doc id in brackets after each "
        "claim, e.g. [policy-001]. If the answer is not in the context, say so.\n\n"
        f"CONTEXT:\n{chunks}\n\n"
        f"QUESTION: {query}\n\nANSWER:"
    )


def main() -> None:
    index, docs = load_artifacts()
    print(f"Loaded index (ntotal={index.ntotal}) and {len(docs)} docs")
    print(f"Loading embedder: {EMBED_MODEL}")
    embedder = SentenceTransformer(EMBED_MODEL)

    client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
    cfg = types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=800,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    queries = [
        "What is the target unpaid rate and how much progress have we made toward it?",
        "How is is_delinquent defined and what is the write-off threshold?",
        "Which merchant segment carries the highest baseline delinquency premium and why?",
        "What do we do when JCIC returns no record for an applicant?",
        "What's the standard process when a quarter's delinquency rate spikes above trailing average?",
    ]

    for i, q in enumerate(queries, 1):
        print("\n" + "=" * 72)
        print(f"Q{i}: {q}")
        retrieved = retrieve(q, index, docs, embedder, k=TOP_K)
        print("Retrieved (top-3):")
        for d, score in retrieved:
            print(f"  score={score:.3f}  [{d['id']}] {d['title']}")
        prompt = build_prompt(q, retrieved)
        resp = client.models.generate_content(
            model=MODEL, contents=prompt, config=cfg
        )
        print("\nAnswer:")
        print(f"  {resp.text.strip()}")

    print("\n" + "=" * 72)
    print("BLOCK 2 COMPLETE ✅")
    print(f"  Embedder: {EMBED_MODEL}")
    print(f"  LLM:      {MODEL} (via google-genai SDK)")
    print(f"  Index:    {INDEX_PATH.name} ({index.ntotal} docs)")
    print("Next: Block 3 (LangGraph agent + BigQuery tool)")


if __name__ == "__main__":
    main()
