# GCP Demo — Block 4 Execution Guide

**Goal**: A Go-written MCP tool that the agent can call. Proves a hands-on Go ramp (Cresta Golang gap) and demonstrates real MCP protocol comprehension — not just "ran an MCP server".
**LoC**: 178 total (`risk.go` 102 + `main.go` 76). Pure Go, one third-party dep.
**Success criteria**: `python demo_client.py` connects to the Go server, lists tools, calls `risk_score` on 3 cases hitting all 3 decision bands, and prints "BLOCK 4 COMPLETE ✅".

---

## Run order

| Step | Command | What |
|---|---|---|
| 1 | `go build -o risk-tool .` | Compile the MCP server (one-time, ~5s) |
| 2 | `pip install mcp --break-system-packages` | Python MCP client SDK |
| 3 | `python demo_client.py` | Spawn the Go server, list tools, call `risk_score` on 3 samples |

---

## What it does

`risk_score` is a rule-based credit-risk scorer derived directly from the policy
docs indexed in Block 2 (`block2/corpus.jsonl`):

| Rule | Source doc | Weight |
|---|---|---|
| Baseline | (portfolio) | +0.10 |
| `is_new_buyer` | policy-001 | +0.10 |
| `segment == travel` | policy-003 | +0.05 |
| `!has_jcic` (alt-data fallback path) | playbook-004 | +0.08 |
| `order_value > segment cap` | policy-003, policy-004 | +0.05 |

Bands: `<0.20` low (approve), `<0.35` medium (review), else high (decline).

This intentionally mirrors the resume claim _"rule-based intervention moved
unpaid rate from 4.5% to 3.5% (~22% relative)"_ — the rules in Go ARE the
intervention.

---

## Architecture

```
┌──────────────────────────┐  spawn (stdio)   ┌─────────────────────────┐
│  Python demo_client.py   │ ───────────────► │  ./risk-tool (Go)       │
│  (mcp.ClientSession)     │ ◄─── JSON-RPC ──┤  mark3labs/mcp-go       │
└──────────────────────────┘                  └─────────────────────────┘
                                                          │
                                                          ▼
                                              ┌────────────────────────┐
                                              │  ScoreRisk(in)         │
                                              │  pure-Go rules         │
                                              │  (risk.go)             │
                                              └────────────────────────┘
```

Why MCP over a plain CLI or REST endpoint:

- The agent (Block 3) is already a "tools and reasoning" architecture. MCP
  gives a uniform interface for adding tools written in **any** language.
- The Go binary is **self-describing**: `tools/list` returns the JSON schema,
  so the agent's planner could be extended to use this tool without code
  changes on the Python side beyond a generic MCP loader.
- Stdio transport keeps deployment trivial (no port management, no auth).

---

## Sample output

```
Connected to MCP server: fintech-risk-tool v0.1.0
Tools exposed: ['risk_score']

CASE: Low-risk: returning retail buyer, has JCIC
  score=0.10  band=low  decision=approve
  contributions:
    - base 0.10 (portfolio baseline)

CASE: Medium-risk: new travel buyer, has JCIC, within cap
  score=0.25  band=medium  decision=review
  contributions:
    - base 0.10 (portfolio baseline)
    - new buyer +0.10 (policy-001)
    - travel segment +0.05 (policy-003)

CASE: High-risk: new travel buyer, NO JCIC, over cap
  score=0.38  band=high  decision=decline
  contributions:
    - base 0.10 (portfolio baseline)
    - new buyer +0.10 (policy-001)
    - travel segment +0.05 (policy-003)
    - no JCIC record +0.08 (playbook-004)
    - order_value 45000 exceeds travel cap 30000 +0.05
```

Each `contributions` line cites the doc id from `block2/corpus.jsonl` so the
risk decision is fully auditable back to written policy.

---

## Files

| File | LoC | Purpose |
|---|---|---|
| `risk.go` | 102 | Pure logic. No MCP imports — unit-testable in isolation |
| `main.go` | 76 | MCP server: tool registration + handler. Single dep: `mark3labs/mcp-go` |
| `demo_client.py` | ~70 | Python client using the official `mcp` SDK |
| `go.mod` / `go.sum` | – | Module + lockfile (checked in for reproducibility) |
| `risk-tool` | – | Compiled binary (gitignored; rebuild with `go build`) |

---

## How Block 3 could integrate this

Out of scope for the demo (would re-touch Block 3 code), but worth flagging
as the natural next step:

```python
# In block3/02_agent.py, add a "risk_executor" node alongside bq_executor:
# Spawn ./block4/risk-tool, expose risk_score to the planner as use_risk=True,
# and add a fourth conditional branch to the LangGraph fan-out.
```

The MCP protocol makes this addition mostly mechanical — the schema is
already discoverable via `tools/list`, so the planner prompt update is the
only meaningful change.

---

## What this means for the JD keywords

| Keyword | Backed by |
|---|---|
| Go production experience | `risk.go` is real Go: typed structs, table-driven rules, error returns, named return values |
| MCP | Real protocol implementation, not just claim. `tools/list` schema visible via raw JSON-RPC probe |
| Tool-calling design | The MCP tool boundary forces a clean schema; same pattern Aaron uses internally with Claude Code + MCP |
| Cross-language agent stacks | Python orchestrator + Go tool over MCP = the cross-stack point the cover letter makes |
