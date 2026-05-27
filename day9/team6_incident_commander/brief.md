# Team 6 — Incident Commander

## Business Context
It's 2:47 AM. Sigma DataTech's pipeline failed in prod. 11 transactions processed, then crash. The on-call engineer is you. You have a stack trace and a DuckDB. You have 15 minutes to declare severity and assign a fix before the CEO wakes up.

## Your Module
Build a Streamlit app that:

**Round 1 — AI First Responder:** Nova Pro reads the stack trace and declares: severity (P1/P2/P3), root cause hypothesis, and recommended immediate fix. Time pressure is part of the scenario.

**Round 2 — AI Devil's Advocate:** Nova Lite generates an *alternative* root cause hypothesis that also explains the stack trace. It argues the Round 1 diagnosis might be wrong.

**Round 3 — Your Investigation:** Run DuckDB queries to determine which hypothesis fits the data. Declare final severity and write the one-line incident summary that goes to the CEO.

## Deliverables
1. Running Streamlit app showing stack trace → hypothesis 1 → hypothesis 2 → investigation
2. The DuckDB queries that ruled out one hypothesis
3. The actual root cause (which may be different from both AI hypotheses)
4. The "What AI Got Wrong" slide — which hypothesis was wrong and why it was plausible

## The Trap
Both AI hypotheses will sound plausible. The data in DuckDB will partially support both. The real root cause requires you to look at something neither AI mentioned. Query the source data, not just the pipeline output.

## Pitch Must Include
- Live demo of the incident response flow
- Your final P1/P2/P3 verdict with justification
- The DuckDB query that cracked the case
- The CEO-ready one-line incident summary
