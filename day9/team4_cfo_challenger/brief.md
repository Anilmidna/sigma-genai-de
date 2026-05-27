# Team 4 — CFO Challenger

## Business Context
Every Monday morning, the CEO of Sigma DataTech gets a 1-page revenue briefing. Today, the DE who writes it is sick. You will use AI to generate it from the Gold layer — but the CFO will challenge every number. One of the AI's insights is confidently wrong.

## Your Module
Build a Streamlit app that:

**Round 1 — AI Briefing Writer:** Nova Pro queries Gold metrics from DuckDB and generates a 5-bullet CEO briefing with specific numbers, trends, and insights.

**Round 2 — CFO Challenge:** Nova Lite plays a skeptical CFO and challenges 3 specific claims from Round 1. For each challenge, it asks: "Show me the data."

**Round 3 — Fact Check:** For each CFO challenge, run the actual DuckDB query to verify or refute the AI's claim. Mark each claim: VERIFIED / WRONG / MISLEADING.

## Deliverables
1. Running Streamlit app showing briefing → challenges → fact-check results
2. The DuckDB queries that prove or disprove each claim
3. The "What AI Got Wrong" slide — the claim that sounds most convincing but is statistically invalid

## The Trap
One of the AI's insights will be mathematically correct but statistically meaningless — a trend based on too few data points to be reliable. The CFO will challenge it. You must explain WHY it's misleading, not just that it's wrong.

## Pitch Must Include
- Live demo of CEO briefing → CFO challenge → fact check
- The claim that failed the fact check and the exact DuckDB result that refutes it
- What additional data you would need to make the insight valid
- A "trust score" for AI-generated business insights (0-100%) with your reasoning
