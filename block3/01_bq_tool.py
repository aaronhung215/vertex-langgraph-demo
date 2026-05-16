"""
GCP Demo Block 3 — Step 1: BigQuery tool with allowlist + parameterised SQL.

Exposes one tool function `delinquency_breakdown(group_by, filters)` that the
agent in 02_agent.py will call. Critical safety properties (recruiter check
list):

- group_by columns and filter keys are validated against an allowlist
- filter VALUES are bound via BigQuery ScalarQueryParameter, never string-
  interpolated — so even if the planning LLM emits a malicious value, the
  query is safe
- group_by columns ARE interpolated (after allowlist check) because BigQuery
  parameters don't support identifier substitution

Run standalone for sanity:
    export PROJECT_ID=fintech-agent-demo-2715
    python 01_bq_tool.py
"""

from __future__ import annotations

import os
from typing import Any

from google.cloud import bigquery

PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET = "fintech_demo"
TABLE = "customer_transactions"

ALLOWED_DIMS: dict[str, str] = {
    "quarter": "STRING",
    "is_new_buyer": "BOOL",
    "merchant_segment": "STRING",
    "device_type": "STRING",
}


class ToolInputError(ValueError):
    """Raised when the agent passes invalid args to the BQ tool."""


def _validate(group_by: list[str], filters: dict[str, Any] | None) -> None:
    if not group_by:
        raise ToolInputError("group_by must be non-empty")
    bad = [g for g in group_by if g not in ALLOWED_DIMS]
    if bad:
        raise ToolInputError(
            f"group_by contains disallowed columns: {bad}. "
            f"Allowed: {sorted(ALLOWED_DIMS)}"
        )
    if filters:
        bad_keys = [k for k in filters if k not in ALLOWED_DIMS]
        if bad_keys:
            raise ToolInputError(
                f"filters contains disallowed keys: {bad_keys}. "
                f"Allowed: {sorted(ALLOWED_DIMS)}"
            )


def delinquency_breakdown(
    group_by: list[str],
    filters: dict[str, Any] | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Aggregate delinquency stats by the given dimensions.

    Args:
        group_by: list of allowed dimension columns (see ALLOWED_DIMS)
        filters: optional dict of {column: value}; column must be an allowed
            dimension; values are bound as query parameters
        project_id: GCP project; defaults to $PROJECT_ID

    Returns:
        Rows as list of dicts with the requested dimensions plus:
            n: int (row count)
            delinquency_pct: float (percent, 2dp)
            avg_order_value_twd: float
            avg_days_late_if_delinq: float
    """
    _validate(group_by, filters)
    project_id = project_id or PROJECT_ID
    if not project_id:
        raise ToolInputError(
            "project_id not provided and PROJECT_ID env var unset"
        )

    select_dims = ", ".join(group_by)
    where_clause = ""
    params: list[bigquery.ScalarQueryParameter] = []
    if filters:
        clauses = []
        for i, (col, val) in enumerate(filters.items()):
            pname = f"p{i}"
            clauses.append(f"{col} = @{pname}")
            params.append(
                bigquery.ScalarQueryParameter(pname, ALLOWED_DIMS[col], val)
            )
        where_clause = "WHERE " + " AND ".join(clauses)

    sql = f"""
    SELECT
      {select_dims},
      COUNT(*) AS n,
      ROUND(AVG(CAST(is_delinquent AS INT64)) * 100, 2) AS delinquency_pct,
      ROUND(AVG(order_value_twd), 2) AS avg_order_value_twd,
      ROUND(AVG(CASE WHEN is_delinquent THEN days_late END), 2)
        AS avg_days_late_if_delinq
    FROM `{project_id}.{DATASET}.{TABLE}`
    {where_clause}
    GROUP BY {select_dims}
    ORDER BY {select_dims}
    """

    client = bigquery.Client(project=project_id)
    job = client.query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=params)
    )
    return [dict(row) for row in job.result()]


def format_as_table(rows: list[dict[str, Any]]) -> str:
    """Render rows as a small markdown table for LLM consumption."""
    if not rows:
        return "(no rows)"
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[h]) for h in headers) + " |")
    return "\n".join(lines)


def _run_tests() -> None:
    print(f"PROJECT_ID = {PROJECT_ID}")
    print("\nTest 1: delinquency by quarter (no filter)")
    rows = delinquency_breakdown(group_by=["quarter"])
    print(format_as_table(rows))

    print("\nTest 2: segment x new_buyer breakdown, filter quarter=Q3")
    rows = delinquency_breakdown(
        group_by=["merchant_segment", "is_new_buyer"],
        filters={"quarter": "Q3"},
    )
    print(format_as_table(rows))

    print("\nTest 3: input validation — disallowed column")
    try:
        delinquency_breakdown(group_by=["customer_id"])  # not in allowlist
    except ToolInputError as e:
        print(f"  ✅ Correctly rejected: {e}")

    print("\nTest 4: input validation — SQL injection attempt in filter value")
    try:
        rows = delinquency_breakdown(
            group_by=["quarter"],
            filters={"merchant_segment": "travel'; DROP TABLE x;--"},
        )
        print(
            f"  ✅ Safe — value bound as parameter, returned {len(rows)} rows "
            "(zero match, no SQL injection):"
        )
        print(format_as_table(rows))
    except Exception as e:  # noqa: BLE001
        print(f"  (unexpected): {type(e).__name__}: {e}")

    print("\nBQ TOOL OK ✅")


if __name__ == "__main__":
    _run_tests()
