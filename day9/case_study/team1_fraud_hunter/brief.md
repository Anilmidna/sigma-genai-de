# Team 1 — Fraud Hunter

## Business Context
Sigma DataTech processes thousands of transactions daily. The fraud team flags suspicious transactions manually — a 2-hour job. Your mission: build an AI-powered fraud detector that flags in seconds. But there's a catch: every false positive = an angry legitimate customer whose card gets blocked.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Prosecutor:** Nova Pro reviews all transactions and flags suspicious ones with severity (CRITICAL / HIGH / MEDIUM) and a one-line reason.

**Round 2 — AI Defense Lawyer:** Nova Lite argues why each flagged transaction might be *legitimate*. It will challenge your Round 1 flags.

**Round 3 — Your Verdict:** For each transaction, you decide: FRAUD / LEGITIMATE / INVESTIGATE. You must set a false-positive threshold and defend it in your pitch.

## Deliverables
1. Running Streamlit app with all 3 rounds
2. A DuckDB query that counts how many legitimate customers would be blocked at your threshold
3. The "What AI Got Wrong" slide — find at least one flag where the AI was confidently wrong

## The Trap
Something in the dataset will break a naive fraud detection approach. You'll know you've hit it when your Round 2 defense lawyer makes a surprisingly strong argument. Dig into the data.

## Pitch Must Include
- Live demo of all 3 rounds
- Your chosen false-positive threshold and the business justification
- One transaction where AI prosecutor and AI defense lawyer completely contradict each other
- What you would do differently with more time
