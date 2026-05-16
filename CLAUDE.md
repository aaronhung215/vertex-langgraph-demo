# CLAUDE.md — Repo Rules for Claude Code

> This file is auto-read by Claude Code at session start. It coordinates work
> between Claude Code (this IDE) and the chat-Claude (claude.ai, which holds
> Aaron's job-search memory + calibrated facts + tracker).

---

## WHO DOES WHAT (read this first)

There are TWO Claudes working with Aaron. They do NOT share context.

| Task type | Owner | Why |
|---|---|---|
| GCP demo code, build, debug, deploy | **You (Claude Code)** | You're strong at this; code doesn't need job-search memory |
| Resume text, cover letters, essays, JD evaluation | **chat-Claude only** | Needs calibrated facts + career vision + tracker that ONLY chat-Claude has |
| Tracker updates, cross-session merge | **chat-Claude only** | chat-Claude has full job-search context + memory |

**You (Claude Code) must NOT edit, rewrite, or "improve" any resume / cover
letter / essay / LinkedIn / job-application text.** If asked, respond:
"That's chat-Claude's domain — it has the calibrated facts I don't. I'll stick
to the demo code." Reason: there are 8 calibrated capability facts (CTR figures,
removed claims, etc.) you don't have — editing job text risks reintroducing
errors that took multiple sessions to fix.

---

## SESSION START PROTOCOL

At the start of every session, before doing anything:

1. Read `_sync/aaron_job_search_progress.md` (the source-of-truth tracker — for
   context only; do NOT modify it)
2. Read `_sync/gcp_demo_weekend_plan.md` (the demo build plan — Blocks 1-6)
3. Read `_sync/claude_code_log.md` (what previous Claude Code sessions did)
4. Then proceed with the user's request

---

## SESSION END PROTOCOL

Before ending a session, append an entry to `_sync/claude_code_log.md`:

```
## <YYYY-MM-DD HH:MM> — <one-line summary>
- Completed: <what got done>
- Files changed/added: <list>
- Errors hit + fixes: <if any>
- Pending / blocked: <what's left>
- Note for chat-Claude: <anything chat-Claude needs to merge into the tracker>
```

This is how Aaron carries your progress back to chat-Claude (he pastes this log
into the chat; chat-Claude merges it into the tracker).

---

## CURRENT TASK: GCP DEMO

Build plan is `_sync/gcp_demo_weekend_plan.md`. 6 blocks, ~16-19h total.
Block files live in `blockN/` folders.

**Block 1** (`block1/`): GCP setup + Vertex AI Gemini + BigQuery synthetic data.
Follow `block1/README.md` execution order.

Key environment facts:
- PROJECT_ID = `fintech-agent-demo-2715`
- Billing account linked, Vertex AI available
- $5 budget alert set
- gcloud CLI installed

Cost discipline: this demo's realistic spend is < USD 2. Do NOT run redundant
Gemini test calls. `03_vertex_hello.py` once-success is enough — don't loop it.

Commit discipline: commit after each block locally. Do NOT `git push` to public
until Block 4 is done (avoid recruiters seeing a half-built repo — recruiters
will Google Aaron's name and this repo backs his resume/cover-letter claims).

---

## SHELL NOTES

Aaron previously hit `export: not valid` errors. Handle shell syntax yourself —
detect the shell, use correct syntax (bash/zsh `export VAR=val`, fish
`set -x VAR val`). Always verify env vars are set in the SAME shell before
running python scripts that depend on them (especially PROJECT_ID).

---

## WHAT NOT TO DO

- Do NOT modify `_sync/aaron_job_search_progress.md` (read-only context for you)
- Do NOT touch resume/cover-letter/essay/LinkedIn/JD text
- Do NOT push to public git until Block 4+
- Do NOT fine-tune anything (time trap, JD doesn't need it)
- Do NOT over-engineer UI (recruiter cares about architecture + written analysis)
- Do NOT run extra paid API calls "to be thorough" — cost-sensitive
