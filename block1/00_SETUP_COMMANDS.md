# GCP Demo — Block 1 Setup Commands (Steps 1-2)

> Run these in order. Each block is copy-paste-able. Stop and fix if any errors before next block.
> Target: ~35-50 min for steps 1-2 (GCP project + billing + APIs + CLI auth).

---

## PREREQUISITE CHECK (2 min — do this FIRST)

```bash
# Do you have gcloud CLI installed?
gcloud --version
```

- ✅ Shows version → skip to STEP 1
- ❌ "command not found" → install first:

**macOS**:
```bash
brew install --cask google-cloud-sdk
```

**Or universal installer** (any OS):
```bash
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
```

---

## STEP 1 — GCP Project + Billing + APIs (~20-30 min)

### 1a. Log in
```bash
gcloud auth login
```
(Opens browser. Log in with the Google account that has billing.)

### 1b. Create project
```bash
# Project IDs must be globally unique. Adjust if taken.
export PROJECT_ID="fintech-agent-demo-$(date +%s | tail -c 5)"
gcloud projects create $PROJECT_ID --name="FinTech Agent Demo"
gcloud config set project $PROJECT_ID
echo "PROJECT_ID = $PROJECT_ID   <-- WRITE THIS DOWN"
```

### 1c. Link billing
```bash
# List your billing accounts
gcloud billing accounts list
```
Copy the `ACCOUNT_ID` (format: XXXXXX-XXXXXX-XXXXXX), then:
```bash
export BILLING_ACCOUNT="PASTE_YOUR_ACCOUNT_ID_HERE"
gcloud billing projects link $PROJECT_ID --billing-account=$BILLING_ACCOUNT
```

> ⚠️ If you have NO billing account: go to https://console.cloud.google.com/billing
> → "Create account" → new GCP users get $300 free credit. This step can take 5-10 min.

### 1d. Set a billing alert tripwire (USD 10)
```bash
# Optional but recommended — do via console if CLI errors:
# https://console.cloud.google.com/billing → Budgets & alerts → Create budget → $10
echo "Set $10 budget alert manually in console if needed"
```

### 1e. Enable required APIs
```bash
gcloud services enable \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  cloudresourcemanager.googleapis.com
echo "APIs enabled — wait 1-2 min for propagation"
```

---

## STEP 2 — CLI auth for application code (~10-15 min)

### 2a. Application Default Credentials (so Python SDK can auth)
```bash
gcloud auth application-default login
```
(Opens browser again. This is different from 1a — it sets up creds the Python SDK reads.)

### 2b. Set quota project (avoids a common SDK warning)
```bash
gcloud auth application-default set-quota-project $PROJECT_ID
```

### 2c. Set region env (Vertex AI needs a region)
```bash
export GCP_REGION="us-central1"
export PROJECT_ID=$PROJECT_ID   # re-export if new terminal
echo "PROJECT_ID=$PROJECT_ID REGION=$GCP_REGION"
```

> 💡 Write PROJECT_ID somewhere — you'll need it in the Python scripts (Step 3-4).

---

## CHECKPOINT before Step 3-4

Run this — all should succeed:
```bash
gcloud config get-value project        # shows your PROJECT_ID
gcloud services list --enabled | grep -E "aiplatform|bigquery"   # shows 2 lines
gcloud auth application-default print-access-token | head -c 20   # shows a token prefix
```

If all 3 OK → proceed to Step 3 (`01_generate_data.py`).
