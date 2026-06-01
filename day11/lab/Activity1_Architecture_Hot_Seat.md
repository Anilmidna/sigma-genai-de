# Activity 1 — Architecture Hot Seat
## 3:15 PM – 4:00 PM | 45 minutes

---

## Setup (before 3:15 PM)

- Whiteboard or large paper per team (or A3 sheets if no whiteboard)
- Markers — at least 2 colours per team
- Print the 4 Scenario Cards below (one per team — cut them out)
- Keep the Scoring Rubric in your hand — do not project it

**Announce:**
> "Laptops closed. Markers out. You have 15 minutes to draw your agent's decision flow
> for the scenario on your card. I will walk around and ask hard questions.
> One person draws, everyone defends. Go."

---

## The Drawing Template (project this on Smart TV)

```
┌─────────────────────────────────────────────────────────────┐
│  SIGMA DATATECH — AGENT DECISION FLOW                       │
│  Team: ____________    Scenario: ____________               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [DATA SOURCE]  →  [AGENT 1]  →  Decision?                 │
│                        ↓                                    │
│                  Yes ──┤── No                               │
│                        ↓                                    │
│                 [AGENT 2 / ACTION]                          │
│                        ↓                                    │
│                  [FINAL OUTPUT]                             │
│                                                             │
│  Draw YOUR version below. Show:                             │
│  • Every agent in the flow                                  │
│  • Every decision point (diamond shape)                     │
│  • What happens when something FAILS                        │
│  • Where the human enters the loop                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Scenario Cards (print and cut — one per team)

---

### CARD A — Team 1 & 2

**Scenario: The Midnight Merchant**

At 11:58 PM a new merchant partner — PayEasy — sends their first CSV.
Schema has never been seen before.
File has 80,000 rows.
Firehose delivers it to S3 at 00:03 AM.

**Draw the agent decision flow that handles this file autonomously.
Include: schema detection, quality check, PII scan, load decision.
Show what happens if quality check fails at 1 AM with no human available.**

Key question Anil will ask:
*"Your quality agent quarantined 15% of rows. It is 1 AM. Load the 85% or wait for human approval?"*

---

### CARD B — Team 3 & 4

**Scenario: The Shape-Shifter**

Sigma DataTech's biggest merchant — QuickMart — upgraded their POS system.
Their transaction feed now sends 3 new columns and renamed `merchant_id` to `store_code`.
This happens mid-day. 50,000 records already loaded with old schema.
Next 50,000 arrive with new schema.

**Draw the agent decision flow that detects the drift, handles both schemas,
and ensures Snowflake Gold table stays consistent.
Show where existing data and new data merge correctly.**

Key question Anil will ask:
*"Your schema agent patched the Silver table. 4 downstream dbt models reference merchant_id. Do they break? Who is responsible?"*

---

### CARD C — Team 5 & 6

**Scenario: The Silent PII Leak**

A partner sends a CSV labelled "merchant_performance_report.csv".
Looks like aggregate data — no PII expected.
But column 7 is named `rep_mob` and contains mobile numbers of merchant representatives.
Column 12 is `mgr_pan` — manager PAN numbers.

Regex scan returns zero PII (abbreviated names).
File is 200,000 rows. Already 40% loaded to Silver before anyone notices.

**Draw the agent flow that would have caught this BEFORE loading.
Show the two-layer detection. Show what happens to the 40% already loaded.**

Key question Anil will ask:
*"The 40% is already in Silver. Compliance asks you to prove no PII reached Gold. Can you? How?"*

---

### CARD D — Team 7, 8 & 9

**Scenario: The Cascading Failure**

Pipeline runs at 6 AM daily. Today:
- Bedrock is throttling (too many API calls from all teams)
- Quality agent cannot generate GE expectations
- Falls back to last known GE suite from 3 weeks ago
- That old suite has no rule for `upi_ref_id` (new column added 2 weeks ago)
- 12,000 records with null `upi_ref_id` load to Silver unchecked
- Gold table aggregations are wrong by 8%

**Draw the agent flow with proper fallback logic.
Show: what triggers the fallback, what the fallback does, how the agent alerts,
and how the pipeline recovers without human intervention.**

Key question Anil will ask:
*"Your fallback used a 3-week-old GE suite. How do you make sure that never happens again?"*

---

## Your Walk-Around Questions (pick 2-3 per team)

Use these as you walk. Do not telegraph them — ask mid-drawing.

1. *"Where is your guardrail? What stops this agent from running forever?"*
2. *"Your agent failed at step 3. What state is the pipeline in? Consistent or corrupt?"*
3. *"Show me the human in this flow. Where exactly do they enter?"*
4. *"What happens if Bedrock is down for 4 hours? Draw the fallback."*
5. *"Your schema agent added a nullable column. Who told the dbt team?"*
6. *"Two agents run in parallel. One finishes in 2 minutes. One takes 45. What happens to the fast one while it waits?"*
7. *"You quarantined 200 rows. Where do they go? Who reviews them? When?"*
8. *"This pipeline runs at 6 AM. At 6:03 AM the business analyst opens the dashboard. Is the data fresh? How do you know?"*

---

## Scoring Rubric (keep in your hand — do not project)

| Criteria | 0 | 1 |
|---|---|---|
| Decision points shown | No diamonds / decision nodes | Every branch has a clear yes/no |
| Failure handling | Pipeline just stops | Fallback or escalation path drawn |
| Human in the loop | Not shown | Clearly marked where + when |

**Max: 3 stars per team.**

Announce winner after all teams present (30 seconds each — one person, one sentence per agent).

---

## Debrief (last 5 minutes)

Show the best drawing on projector (photo with your phone).

Say:
> "This is what a senior DE draws in a system design interview.
> Not code. Not SQL. A decision flow with failure paths and human escalation points.
> Remember this drawing. You will need it in your first job."

---

## Star Award

- 3/3 criteria: 2 stars
- 2/3 criteria: 1 star
- Best overall (peer vote — show of hands): 1 bonus star
