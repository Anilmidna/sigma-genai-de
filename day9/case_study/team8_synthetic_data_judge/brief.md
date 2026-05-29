# Team 8 — Synthetic Data Judge

## Business Context
Sigma DataTech's test environment uses real production data — a compliance risk. The data team used AI to generate synthetic transactions that "look real." The compliance officer approved it based on statistical similarity. But the QA lead is not convinced. Your job: prove whether this synthetic data is safe to use for testing.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Statistician:** Nova Pro compares synthetic vs real transactions across all dimensions — mean, distribution, cardinality, null rates. Generates a "realism score" (0-100) with statistical justification.

**Round 2 — AI Domain Expert:** Nova Lite reviews the same data but from a business rules perspective — not statistics. It looks for combinations that are statistically possible but impossible in the real world.

**Round 3 — Your Judgement:** Run DuckDB queries to validate the domain expert's concerns. For each impossibility found, classify: CRITICAL (would cause a test to give a false pass) / MINOR (cosmetic issue) / FALSE ALARM.

## Deliverables
1. Running Streamlit app showing statistical comparison → domain review → your judgement
2. The specific impossibilities found with DuckDB proof queries
3. A "safe to use" / "not safe to use" verdict with confidence %
4. The "What AI Got Wrong" slide — how did statistics miss what domain knowledge caught?

## The Trap
The statistical realism score will be high (>80%). All the statistical tests will pass. The impossibilities are invisible to statistics — they require knowledge of how payments actually work in India. Use your own knowledge, not just the AI's output.

## Pitch Must Include
- Live demo of statistician vs domain expert
- Every impossibility found with DuckDB proof
- Your final SAFE / NOT SAFE verdict
- What "good synthetic data" would require that AI alone cannot provide
