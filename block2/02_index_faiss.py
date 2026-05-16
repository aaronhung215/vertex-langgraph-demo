"""
GCP Demo Block 2 — Step 2: Embed corpus with sentence-transformers + FAISS.

Reads corpus.jsonl, embeds title+text with all-MiniLM-L6-v2 (384-dim),
normalizes vectors for cosine similarity via IndexFlatIP, and persists:
    faiss_index.bin   — the FAISS index
    doc_meta.jsonl    — id->title/text mapping in the same order as the index

Sentence-transformers + FAISS chosen over Vertex AI Vector Search for speed
of setup (per gcp_demo_weekend_plan.md). README mentions both as the
architectural alternative.

Run:
    pip install sentence-transformers faiss-cpu --break-system-packages
    python 02_index_faiss.py
"""

import json
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

HERE = Path(__file__).parent
CORPUS = HERE / "corpus.jsonl"
INDEX_OUT = HERE / "faiss_index.bin"
META_OUT = HERE / "doc_meta.jsonl"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(
            f"{CORPUS.name} not found. Run 01_build_corpus.py first."
        )

    docs = [json.loads(line) for line in CORPUS.read_text().splitlines() if line]
    print(f"Loaded {len(docs)} docs from {CORPUS.name}")

    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    texts = [f"{d['title']}. {d['text']}" for d in docs]
    embs = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    ).astype(np.float32)
    print(f"Embeddings shape: {embs.shape}")

    # IndexFlatIP with normalized vectors == cosine similarity
    index = faiss.IndexFlatIP(embs.shape[1])
    index.add(embs)
    faiss.write_index(index, str(INDEX_OUT))
    print(f"Wrote FAISS index: {INDEX_OUT.name} (ntotal={index.ntotal})")

    with META_OUT.open("w") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")
    print(f"Wrote doc metadata: {META_OUT.name}")

    # Sanity retrieval test (no LLM call)
    print("\nSanity retrieval test (no LLM):")
    test_queries = [
        "What is the target unpaid rate?",
        "How do we handle applicants with no JCIC record?",
        "Why does Q3 delinquency spike?",
    ]
    q_embs = model.encode(
        test_queries, normalize_embeddings=True
    ).astype(np.float32)
    D, I = index.search(q_embs, k=2)
    for q, dists, idxs in zip(test_queries, D, I):
        print(f"\n  Q: {q}")
        for rank, (dist, i) in enumerate(zip(dists, idxs), 1):
            print(f"    #{rank} score={dist:.3f}  [{docs[i]['id']}] {docs[i]['title']}")


if __name__ == "__main__":
    main()
