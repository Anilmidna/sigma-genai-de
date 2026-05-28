# Team 2 — Data Therapist

## Business Context
Sigma DataTech's Bronze layer ingests raw transactions from 3 source systems. Quality is terrible — nulls, negatives, duplicates. The data team spends 3 hours each morning manually diagnosing issues. Your AI therapist diagnoses AND prescribes fixes automatically.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Diagnosis:** Nova Pro scans dirty transactions and diagnoses each quality issue: what's wrong, why it happened (root cause hypothesis), and confidence score.

**Round 2 — AI Prescription:** Nova Lite prescribes a specific fix for each issue (SQL or Python). But it will also generate a "side effect warning" — what could go wrong if you apply this fix blindly.

**Round 3 — Your Treatment Plan:** For each issue, decide: APPLY FIX / REJECT FIX / NEEDS INVESTIGATION. Run the fix against DuckDB and show before/after row counts.

## Deliverables
1. Running Streamlit app with all 3 rounds
2. DuckDB before/after comparison showing the impact of your approved fixes
3. The "What AI Got Wrong" slide — find the fix that causes more damage than it heals

## The Trap
At least one AI-prescribed fix will look obviously correct but will break something downstream. You won't see the breakage until you query the Silver table after applying it. Check the downstream impact, not just the fix itself.

## Pitch Must Include
- Live demo of diagnosis → prescription → treatment
- The fix you rejected and why
- How many rows survived to Silver after your treatment plan
- What "healthy data" looks like for Sigma DataTech
