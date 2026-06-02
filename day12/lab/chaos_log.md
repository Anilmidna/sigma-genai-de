# Chaos Log — Team Name: _______________
## Day 12 | Wednesday 4 June 2026

---

## Pre-Exercise Answer (fill before Phase 1)

**Question:** Should the 9 tool functions be one Lambda or separate Lambdas? What breaks if they are one?

**Your answer:**

---

## Phase 2 — Manual Investigation

*You have 60 minutes. Find the root cause before the agents do.*

**Records in Kinesis (02:00–02:20 UTC):** _____ records sent

**Records in S3 (02:00–02:20 UTC):** _____ files, _____ bytes total

**Records in Snowflake (02:00–02:20):** _____ rows loaded

---

**Failure timestamp:** _____ UTC (exact, from CloudWatch)

**What changed at that timestamp:**

**Root cause (your hypothesis):**

**Why no alert fired:**

**Time taken to find this:** _____ minutes

---

**Signals you connected:**

**Signal you missed (fill this in Phase 3 after seeing the agent output):**

---

## Phase 3 — Comparison

**What I found (Phase 2 manual):**
- Time taken: _____ minutes
- Root cause found? Yes / No / Partial
- SLA breach identified? Yes / No
- Prevention created? Yes / No

**What the agent found (Phase 3):**
- Time taken: _____ seconds
- Root cause found? Yes
- SLA breach identified? Yes
- Prevention created? Yes (3 live alarms)

**What I missed that the agent caught:**

**Why the agent caught it:**

---

## Judgment Questions

**Forensics Agent:**
*The agent found the root cause by correlating Lambda version history with Snowflake query history. What is the one CloudWatch alarm that would have caught this at 02:12 instead of 09:03? Write it as a metric alarm definition.*

Your answer:

---

**Recovery Agent:**
*The recovery used transaction_id as the idempotency key. What happens if a legitimate duplicate transaction_id exists in the source data? How would you change the deduplication logic?*

Your answer:

---

**Hardening Agent:**
*The sigma-lambda-version-change alarm fires on any Lambda error spike after a version change. Your team deploys 20 Lambda functions per day in prod. Would you keep this alarm? If yes, how do you stop it from spamming? If no, what replaces it?*

Your answer:

---

## Your Honest Reflection

**Which part of the manual investigation took longest and why:**

**What would have happened if this hit prod at 2 AM with no agents:**

**One thing you would add to this platform that none of the 6 agents currently do:**

---

*Push this file to your team fork before the Phase 2 checkpoint.*
*Incomplete answers are flagged by validate_day12.py*
