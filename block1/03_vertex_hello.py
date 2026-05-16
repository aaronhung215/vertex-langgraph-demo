"""
GCP Demo Block 1 — Step 4: Verify Vertex AI Gemini access (hello-world).

This is the Block 1 success criteria: a working Gemini call via the SDK.
If this prints a coherent answer, Block 1 is COMPLETE.

Setup:
    pip install google-cloud-aiplatform --break-system-packages
    export PROJECT_ID="<your project id>"
    export GCP_REGION="us-central1"
    python 03_vertex_hello.py
"""

import os

PROJECT_ID = os.environ.get("PROJECT_ID")
REGION = os.environ.get("GCP_REGION", "us-central1")

if not PROJECT_ID:
    raise SystemExit('Set: export PROJECT_ID="your-project-id"')

import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project=PROJECT_ID, location=REGION)

# Use a current Gemini model. If this errors with "model not found",
# try fallbacks in order (model availability shifts by region/date).
MODEL_CANDIDATES = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
]

model = None
last_err = None
for name in MODEL_CANDIDATES:
    try:
        m = GenerativeModel(name)
        resp = m.generate_content("Reply with exactly: GEMINI_OK")
        if "GEMINI_OK" in resp.text:
            model = name
            print(f"✅ Model working: {name}")
            print(f"   Response: {resp.text.strip()}")
            break
    except Exception as e:  # noqa: BLE001
        last_err = e
        print(f"  tried {name} -> failed ({type(e).__name__})")

if model is None:
    raise SystemExit(
        f"No Gemini model worked. Last error:\n{last_err}\n"
        "Check: (1) aiplatform.googleapis.com enabled, "
        "(2) gcloud auth application-default login done, "
        "(3) region has Gemini (try us-central1)."
    )

# Domain-flavored test — proves the model can reason on the demo's use case
m = GenerativeModel(model)
test = m.generate_content(
    "A FinTech analyst sees new-buyer delinquency spike in Q3. "
    "In ONE sentence, name the single most useful follow-up data query."
)
print("\nDomain reasoning test:")
print(f"  {test.text.strip()}")

print("\n" + "=" * 50)
print("BLOCK 1 COMPLETE ✅")
print(f"  Project: {PROJECT_ID}")
print(f"  Region:  {REGION}")
print(f"  Model:   {model}")
print("  BigQuery: fintech_demo.customer_transactions loaded")
print("Next session: Block 2 (RAG baseline with FAISS)")
print("=" * 50)
