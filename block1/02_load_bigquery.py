"""
GCP Demo Block 1 — Step 3b: Create BigQuery dataset + load synthetic data.

Run AFTER 01_generate_data.py (needs customer_transactions.csv).

Setup:
    pip install google-cloud-bigquery pandas pandas-gbq --break-system-packages
    export PROJECT_ID="<your project id from setup step 1b>"
    python 02_load_bigquery.py

Creates:
    dataset:  fintech_demo
    table:    fintech_demo.customer_transactions   (~10,000 rows)
"""

import os
from google.cloud import bigquery

PROJECT_ID = os.environ.get("PROJECT_ID")
if not PROJECT_ID:
    raise SystemExit(
        "PROJECT_ID env var not set. Run:\n"
        '  export PROJECT_ID="your-project-id"\n'
        "then re-run this script."
    )

DATASET = "fintech_demo"
TABLE = "customer_transactions"
CSV = "customer_transactions.csv"

client = bigquery.Client(project=PROJECT_ID)

# 1. Create dataset (idempotent)
dataset_ref = f"{PROJECT_ID}.{DATASET}"
ds = bigquery.Dataset(dataset_ref)
ds.location = "US"
ds = client.create_dataset(ds, exists_ok=True)
print(f"Dataset ready: {dataset_ref}")

# 2. Load CSV with autodetect schema, replace if exists
table_ref = f"{dataset_ref}.{TABLE}"
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.CSV,
    skip_leading_rows=1,
    autodetect=True,
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
)

with open(CSV, "rb") as f:
    load_job = client.load_table_from_file(
        f, table_ref, job_config=job_config
    )
load_job.result()  # wait

table = client.get_table(table_ref)
print(f"Loaded {table.num_rows} rows into {table_ref}")

# 3. Sanity query — the exact insight the demo agent will surface
query = f"""
SELECT
  quarter,
  is_new_buyer,
  COUNT(*) AS n,
  ROUND(AVG(CAST(is_delinquent AS INT64)) * 100, 2) AS delinquency_pct
FROM `{table_ref}`
GROUP BY quarter, is_new_buyer
ORDER BY quarter, is_new_buyer
"""
print("\nSanity query — delinquency by quarter x new_buyer:")
for row in client.query(query).result():
    flag = "new" if row.is_new_buyer else "returning"
    print(
        f"  {row.quarter} {flag:9s}  n={row.n:5d}  "
        f"delinquency={row.delinquency_pct}%"
    )

print(f"\nDONE. Table: {table_ref}")
print("Next: 03_vertex_hello.py (verify Gemini access)")
