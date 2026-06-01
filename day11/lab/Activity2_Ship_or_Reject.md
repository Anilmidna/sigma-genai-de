# Activity 2 — Ship or Reject
## 4:30 PM – 5:30 PM | 60 minutes

---

## Setup (before 4:30 PM)

- Project the Incident Brief on Smart TV (below)
- Print Decision Cards — one per team (or teams write on paper)
- Wheel of Names ready
- Keep the Verdict Script in your hand

**Announce:**
> "This is real. This happened at a fintech last year.
> You have 10 minutes to read the brief as a team and fill your decision card.
> One decision. One justification. One sentence each. Then we go team by team."

---

## THE INCIDENT BRIEF
### Project this on Smart TV — keep it up the whole activity

```
╔══════════════════════════════════════════════════════════════╗
║         SIGMA DATATECH — PIPELINE INCIDENT REPORT           ║
║                   Monday 2 June 2026 | 09:47 AM             ║
╠══════════════════════════════════════════════════════════════╣
║                                                             ║
║  FILE PROCESSED:  transactions_raw_20260602.csv             ║
║  RECEIVED FROM:   QuickMart Merchant API                    ║
║  TOTAL RECORDS:   4,847                                     ║
║                                                             ║
║  QUALITY AGENT REPORT:                                      ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │ Expectations generated : 11                        │    ║
║  │ Checks passed          : 8                         │    ║
║  │ Checks FAILED          : 3                         │    ║
║  │                                                    │    ║
║  │ CRITICAL: 23 null transaction_ids    → QUARANTINED │    ║
║  │ HIGH:     12 negative amounts        → QUARANTINED │    ║
║  │ MEDIUM:   6 unknown currency (XYZ)   → QUARANTINED │    ║
║  │                                                    │    ║
║  │ Auto-fix applied: whitespace stripped              │    ║
║  │ Clean rows:       4,806  (99.2%)                   │    ║
║  │ Quarantined:      41     (0.85%)                   │    ║
║  │                                                    │    ║
║  │ LOAD DECISION:  quarantine_and_load                │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                             ║
║  PII AGENT REPORT:                                          ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │ PII columns found: 0                               │    ║
║  │ Dataset sensitivity: INTERNAL                      │    ║
║  │ Load restriction: None                             │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                             ║
║  SCHEMA AGENT REPORT:                                       ║
║  ┌────────────────────────────────────────────────────┐    ║
║  │ Drift detected: NO                                 │    ║
║  │ Schema matches baseline                            │    ║
║  └────────────────────────────────────────────────────┘    ║
║                                                             ║
╠══════════════════════════════════════════════════════════════╣
║  THE SITUATION:                                             ║
║                                                             ║
║  It is 9:47 AM. Board meeting at 10:30 AM.                  ║
║  CFO needs yesterday's GMV numbers on the dashboard.        ║
║  This file IS yesterday's transactions.                     ║
║                                                             ║
║  THREE PEOPLE ARE IN YOUR SLACK RIGHT NOW:                  ║
║                                                             ║
║  📱 Tech Lead (Priya):                                      ║
║     "0.85% quarantine rate is fine. Load it.               ║
║      We cannot miss the board meeting."                     ║
║                                                             ║
║  📱 Compliance Officer (Rajan):                             ║
║     "23 null transaction_ids means we cannot audit          ║
║      those 23 transactions. Block the load.                 ║
║      Regulatory requirement — every transaction             ║
║      must be traceable."                                    ║
║                                                             ║
║  📱 Business Analyst (Meera):                               ║
║     "Just load everything including quarantine.             ║
║      I will filter out the bad rows in my dashboard.        ║
║      I need ALL the data."                                  ║
║                                                             ║
╠══════════════════════════════════════════════════════════════╣
║  YOUR DECISION:                                             ║
║                                                             ║
║  What do you do? You have 10 minutes.                       ║
╚══════════════════════════════════════════════════════════════╝
```

---

## Decision Card (teams fill this in — print or write on paper)

```
╔══════════════════════════════════════════════╗
║  SHIP OR REJECT — TEAM DECISION CARD         ║
║  Team Name: ___________________________      ║
╠══════════════════════════════════════════════╣
║                                              ║
║  OUR DECISION (circle one):                  ║
║                                              ║
║    LOAD CLEAN    |   BLOCK ALL   |   OTHER   ║
║                                              ║
║  Justification (1 sentence):                 ║
║  ________________________________________    ║
║  ________________________________________    ║
║                                              ║
║  Who are you siding with?                    ║
║    □ Priya (Tech Lead)                       ║
║    □ Rajan (Compliance)                      ║
║    □ Meera (Business Analyst)                ║
║    □ None — our own call                     ║
║                                              ║
║  One guardrail you would add to the agent    ║
║  to prevent this situation next time:        ║
║  ________________________________________    ║
║  ________________________________________    ║
╚══════════════════════════════════════════════╝
```

---

## Running the Activity (after 10 minutes)

**Round 1 — Wheel of Names (20 minutes)**

Spin for each team. That person reads out:
1. Their decision (LOAD / BLOCK / OTHER)
2. Their justification (one sentence only — cut them off if they ramble)
3. Which stakeholder they sided with

Do NOT give your verdict yet. Just acknowledge. Move to next team.

After all 9 teams — ask:
> "Show of hands — how many said LOAD CLEAN?"
> "How many said BLOCK ALL?"
> "How many said something else?"

Usually it is 5-4 or 6-3. Perfect tension for the verdict.

---

## Your Verdict Script (read this yourself — do not project)

**THE RIGHT ANSWER:**

Load 4,806 clean rows. Block the 41 quarantined rows. Do NOT load everything.

**Why Priya is partially right:** 0.85% quarantine rate is low. The clean data should go to the board meeting dashboard. Blocking everything for 0.85% of records is disproportionate.

**Why Rajan is right on the compliance point:** The 23 null transaction_ids cannot be loaded to any system — ever. They are unauditable. Loading them and then "filtering in the dashboard" (Meera's suggestion) means they exist in the database. That is a compliance violation even if they never appear on screen.

**Why Meera is completely wrong:** Loading bad data to a warehouse so the analyst can filter it is the worst pattern in data engineering. You have now loaded PII, nulls, and invalid records into a system that has backups, audit logs, and replicas. "Filtering in the dashboard" does not remove the data from the warehouse.

**The guardrail that prevents this situation:** A load threshold SLA — defined BEFORE the pipeline runs, not in a crisis. Example: "If quarantine_pct < 2% AND no CRITICAL failures, load clean rows automatically. If quarantine_pct >= 2% OR any CRITICAL failure, page the on-call DE."

That SLA should be a config parameter in the agent. Not a Slack argument at 9:47 AM.

---

**Say this to close:**

> "In production, the agent should have made this decision automatically
> based on a pre-agreed SLA — not at 9:47 AM with three people arguing in Slack.
> The Slack argument is a symptom of missing governance.
> The agent is not the problem. The missing config is the problem.
> That is what you fix BEFORE go-live."

---

## Star Award

- Correct decision (load clean, block quarantine): 1 star
- Best guardrail suggestion (peer vote — show of hands): 1 bonus star
- Team whose member gives the best verbal defense (Anil's pick): 1 star
