"""
GCP Demo Block 1 — Step 3a: Generate synthetic FinTech delinquency dataset.

Produces a 10,000-row CSV mirroring Aaron's NP credit-risk domain so the demo
story is a clean extension of the resume story (NOT a different toy problem).

Schema deliberately echoes:
- new vs returning buyer (NP first-time-buyer LR model)
- Q1-Q4 quarter (NP "Q1-Q4 delinquency discrimination")
- delinquency / unpaid flag (NP 4.5%->3.5% unpaid rate work)
- merchant segment travel/gaming/retail (NP merchant-segment parameter work)

Run:
    pip install faker pandas --break-system-packages
    python 01_generate_data.py
Output: customer_transactions.csv  (~10,000 rows)
"""

import random
import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

N = 10_000
SEGMENTS = ["travel", "gaming", "retail"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

rows = []
for i in range(N):
    customer_id = f"CUST{i:06d}"
    is_new_buyer = random.random() < 0.42  # ~42% first-time buyers
    segment = random.choices(SEGMENTS, weights=[0.30, 0.33, 0.37])[0]
    quarter = random.choice(QUARTERS)

    # Base order value differs by segment
    base = {"travel": 8500, "gaming": 1800, "retail": 3200}[segment]
    order_value = round(max(200, random.gauss(base, base * 0.45)), 2)

    # Delinquency probability: new buyers + travel + Q3 spike higher (story hook)
    p_delinq = 0.035
    if is_new_buyer:
        p_delinq += 0.020
    if segment == "travel":
        p_delinq += 0.010
    if quarter == "Q3":
        p_delinq += 0.015  # the "Q3 spike" the demo agent will explain
    p_delinq = min(p_delinq, 0.20)

    is_delinquent = random.random() < p_delinq
    days_late = (
        random.choice([7, 14, 30, 45, 60, 90]) if is_delinquent else 0
    )

    rows.append(
        {
            "customer_id": customer_id,
            "transaction_date": fake.date_between(
                start_date="-1y", end_date="today"
            ).isoformat(),
            "quarter": quarter,
            "is_new_buyer": is_new_buyer,
            "merchant_segment": segment,
            "order_value_twd": order_value,
            "is_delinquent": is_delinquent,
            "days_late": days_late,
            "credit_limit_twd": random.choice(
                [10000, 20000, 30000, 50000, 80000]
            ),
            "device_type": random.choice(["ios", "android", "web"]),
        }
    )

df = pd.DataFrame(rows)
df.to_csv("customer_transactions.csv", index=False)

# Quick sanity print
overall = df["is_delinquent"].mean()
new_rate = df[df.is_new_buyer]["is_delinquent"].mean()
q3_rate = df[df.quarter == "Q3"]["is_delinquent"].mean()
print(f"Rows: {len(df)}")
print(f"Overall delinquency: {overall:.3%}")
print(f"New-buyer delinquency: {new_rate:.3%}")
print(f"Q3 delinquency (the spike the agent explains): {q3_rate:.3%}")
print("Saved -> customer_transactions.csv")
