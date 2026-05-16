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

## State graph

```
START
  │
  ▼
┌──────────┐  emits JSON: {use_rag, use_bq, bq_args, reasoning}
│ planner  │  (gemini-2.5-flash, response_mime_type=application/json)
└──────────┘
  │
  ├──────────────────────┐         ← fan out (parallel)
  ▼                      ▼
┌───────────┐    ┌──────────────┐
│ retriever │    │ bq_executor  │  ← BigQuery via parameterised SQL,
│ (FAISS)   │    │ (allowlisted │     allowlisted dimensions/filters
└───────────┘    └──────────────┘
  │                      │
  └──────────┬───────────┘         ← fan in (synthesizer waits for both)
             ▼
        ┌──────────────┐
        │ synthesizer  │  citations: [doc-id] + "(per the data table)"
        └──────────────┘
             │
             ▼
        ┌──────────────┐
        │ reflection   │  self-check; outputs "OK" or one-line fix
        └──────────────┘
             │
             ▼
            END
```

Three test queries trigger three different paths:

| # | Question | use_rag | use_bq |
|---|---|---|---|
| 1 | "What's our target unpaid rate, and how is is_delinquent defined?" | ✅ | ❌ |
| 2 | "Show me delinquency rate broken down by quarter." | ❌ | ✅ |
| 3 | "Q3 new-buyer delinquency feels high. What does the data show, and what's our SOP?" | ✅ | ✅ |

---

## Design choices

| Choice | Why |
|---|---|
| **LangGraph with plain-Python nodes** (no LangChain ChatModel) | Demonstrates the orchestration pattern without dragging in LangChain's full ecosystem. Each node is a small `(state) -> dict` function — easy to read, easy to unit-test |
| **Planner returns structured JSON** (`response_mime_type=application/json`) | Deterministic routing; planner cannot emit malformed instructions that break downstream nodes |
| **Parallel fan-out** for retriever + bq_executor | Both are independent given the plan. LangGraph merges the resulting state automatically. Measurable latency win when both tools are needed |
| **BQ tool: allowlist + query parameters** | The LLM could be prompt-injected into emitting hostile filter values. Allowlist + `ScalarQueryParameter` makes the worst case "zero rows returned", never SQL injection. `01_bq_tool.py` includes an explicit injection test |
| **Reflection is no-loop** | Just transparency — prints `OK` or one-line critique. A retry loop adds complexity and risks divergence; out of scope for a 16-hr demo |
| **`thinking_budget=0` on all calls** | Routing / synthesis / reflection are simple enough not to need 2.5-flash's hidden reasoning. Saves cost and avoids the token-budget-eaten-by-thinking bug seen in Block 2 |

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
