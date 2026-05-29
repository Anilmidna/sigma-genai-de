# Team 7 — Schema Archaeologist

## Business Context
Sigma DataTech's transaction schema has evolved 3 times in 18 months. Nobody documented why. A new analytics team wants to migrate from v2 to v3 — but a business analyst says "something feels off about that migration." Your AI archaeologist will reconstruct the history and find what's off.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Historian:** Nova Pro compares all 3 schema versions (v1, v2, v3) and writes the "business story" behind each change. What decision or incident caused each schema evolution?

**Round 2 — AI Risk Auditor:** Nova Lite reviews the generated migration SQL (v1→v2 and v2→v3) and assigns a risk score (LOW/MEDIUM/HIGH/CRITICAL) to each migration step, with specific reasons.

**Round 3 — Your Archaeological Finding:** Run DuckDB queries to prove or disprove the Risk Auditor's concerns. Find the migration step that would silently break a downstream report without throwing an error.

## Deliverables
1. Running Streamlit app showing schema diffs → business story → risk audit → your finding
2. The specific downstream query that breaks silently after the dangerous migration
3. A proposed safer migration approach
4. The "What AI Got Wrong" slide — what risk did the AI miss or overstate?

## The Trap
One migration step will be rated MEDIUM risk by the AI but is actually CRITICAL. It won't throw an error — the pipeline will run successfully and return results, just wrong results. You must write the DuckDB query that exposes this.

## Pitch Must Include
- Live demo of schema archaeology
- The dangerous migration step with proof of silent failure
- Your safer migration proposal
- How you would have caught this in a real production environment
