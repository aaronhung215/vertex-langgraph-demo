# GCP Demo — Block 3 Execution Guide

**Goal**: LangGraph agent with parallel RAG + BigQuery tool calling, structured planner, and self-reflection node.
**Time**: 90-120 min including read-through.
**Success criteria**: `02_agent.py` runs 3 end-to-end queries — each exercising a different tool path — and prints "BLOCK 3 COMPLETE ✅".

---

## Run order

| Step | File | What |
|---|---|---|
| 1 | `01_bq_tool.py` | Sanity-test the BQ tool standalone (no LLM). Includes a SQL-injection-attempt test |
| 2 | `02_agent.py` | Run the full LangGraph agent against 3 demo queries |

---

## One-time pip installs

```bash
pip install langgraph langchain-core --break-system-packages
```

(BigQuery client, FAISS, sentence-transformers, google-genai already installed in Block 1-2.)

---

## Quick start

```bash
export PROJECT_ID="fintech-agent-demo-2715"
export GCP_REGION="us-central1"

python 01_bq_tool.py            # 4 standalone tool tests
python 02_agent.py              # 3 e2e queries through the LangGraph
```

---

## State graph & design choices

The full state graph (with fan-out / fan-in mechanics), the `AgentState`
schema, per-node responsibilities, and the design-decision table are
documented in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) — the
repo-level single source of truth. Sections most relevant to Block 3:

- [§ 3 Agent state graph](../ARCHITECTURE.md#3-agent-state-graph)
- [§ 4 AgentState schema](../ARCHITECTURE.md#4-agentstate-schema)
- [§ 5 Per-node responsibilities](../ARCHITECTURE.md#5-per-node-responsibilities)
- [§ 7 Tool safety model](../ARCHITECTURE.md#7-tool-safety-model) (BQ allowlist + parameter binding)
- [§ 9 Design decisions](../ARCHITECTURE.md#9-design-decisions)

The three demo queries triggering three different tool paths:

| # | Question | use_rag | use_bq |
|---|---|---|---|
| 1 | "What's our target unpaid rate, and how is is_delinquent defined?" | ✅ | ❌ |
| 2 | "Show me delinquency rate broken down by quarter." | ❌ | ✅ |
| 3 | "Q3 new-buyer delinquency feels high. What does the data show, and what's our SOP?" | ✅ | ✅ |

---

## What this means for the JD keywords

- **ReAct** = the planner→tool→synth chain (a single ReAct cycle; iterative ReAct would loop reflection → planner)
- **Hierarchical delegation** = the planner is a coordinator that delegates to specialised retrieval / SQL nodes
- **Function/tool calling** = `delinquency_breakdown` is the agent's BigQuery tool; allowlist + parameter binding is the safety story to discuss in interview
- **LangGraph orchestration** = `StateGraph` with parallel branches and a typed `AgentState`

---

## What's next

- **Block 4**: Go MCP tool (~100 lines) — proves a hands-on Go ramp for the Cresta Golang gap, exposed as an MCP-compatible tool the agent could route to
- **Block 5**: Cloud Run + LangSmith — deploy + observability
- **Block 6**: README polish + Mermaid + cross-stack comparison table (Vertex+LangGraph vs Claude Code+MCP)
