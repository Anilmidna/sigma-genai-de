# Team 3 — Pipeline Lawyer

## Business Context
A junior DE submitted a PR to fix the Silver load idempotency bug. The fix looks clean. The tests pass. But the tech lead has a gut feeling something is wrong. Your AI lawyer will argue both sides of this PR. You are the judge.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Prosecutor (PRO-merge):** Nova Pro reads both pipeline versions (v1 and v2) and writes a brief arguing FOR merging the change. It will list every improvement.

**Round 2 — AI Defense (AGAINST-merge):** Nova Lite reads the same code and writes a brief arguing AGAINST merging. It will find risks, edge cases, and potential failures.

**Round 3 — Your Verdict:** APPROVE / REJECT / REQUEST CHANGES. You must write one sentence explaining exactly what you would ask the developer to change.

## Deliverables
1. Running Streamlit app showing both legal briefs side by side
2. A DuckDB query or Python test that demonstrates the flaw you (hopefully) found
3. The "What AI Got Wrong" slide — which argument was weaker, and why?

## The Trap
The v2 fix genuinely solves the original bug. But it introduces a different problem that only appears under a specific condition — one you can reproduce with 5 lines of Python. Think about what happens when this function is called more than once.

## Pitch Must Include
- Live demo of the two legal briefs
- Your APPROVE / REJECT verdict with exact justification
- The 5-line reproduction of the bug (if you found it)
- What the correct fix looks like
