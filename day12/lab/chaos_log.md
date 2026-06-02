# Chaos Log — Team Name: Sigma DataTech — Ataur Rahman
## Day 12 | Wednesday 4 June 2026

---

## Pre-Exercise Answer (fill before Phase 1)

**Question:** Should the 9 tool functions be one Lambda or separate Lambdas? What breaks if they are one?

**Your answer:**

They should be **separate Lambdas** — one per tool. If all 9 tools share a single Lambda, you hit several serious problems:

1. **Blast radius**: A crash or timeout in one tool (e.g., `query_snowflake` hangs waiting for Snowflake) kills every other tool for the duration of that invocation.
2. **Concurrency contention**: All 9 agent tool calls share the same concurrency pool. A spike in `get_kinesis_records` (which replays thousands of records) will throttle unrelated calls like `send_sns_alert`.
3. **Memory and timeout mismatch**: `load_to_snowflake` needs 512MB and a 5-minute timeout; `send_sns_alert` needs 128MB and 3 seconds. A single Lambda must be provisioned for the worst-case combination — wasting memory 90% of the time.
4. **Deployment coupling**: Changing one tool's logic requires redeploying the entire monolith, increasing risk and slowing the feedback loop.
5. **IAM over-permission**: A single Lambda needs ALL permissions (Kinesis, Snowflake secrets, S3, SNS, CloudWatch) — violating least-privilege. Separate Lambdas each get only what they need.

**Conclusion**: Separate Lambdas with the dispatcher pattern (used in this lab) gives independent scaling, isolated IAM, and zero blast radius between tools.

---

## Phase 2 — Manual Investigation

*You have 60 minutes. Find the root cause before the agents do.*

**Records in Kinesis (02:00–02:20 UTC):** 847 records sent

**Records in S3 (02:00–02:20 UTC):** 14 files, 203,480 bytes total

**Records in Snowflake (02:00–02:20):** 0 rows loaded

---

**Failure timestamp:** 02:11 UTC (exact, from CloudWatch — Lambda version change event logged at 02:11:07)

**What changed at that timestamp:**

Lambda `sigma-kinesis-producer` was automatically deployed to **version 2 (v2)** at 02:11 UTC via a CI/CD pipeline trigger. The `LIVE` alias was updated to point to v2 without a manual approval gate. The v2 code introduced two breaking changes: the field `merchant_name` was renamed to `merchant_nm`, and transaction dates were reformatted from `YYYY-MM-DD` to `DD-MM-YYYY`. Firehose continued delivering the v2 output to S3 successfully (no delivery errors), but the Snowflake `COPY INTO` stage silently loaded 0 rows because the schema no longer matched the target table columns.

**Root cause (your hypothesis):**

Lambda v2 introduced a schema mutation (`merchant_name` → `merchant_nm`, date format change) that caused a **silent schema mismatch** in the Snowflake COPY INTO pipeline. The records were produced and delivered to S3 correctly, but Snowflake rejected all rows at load time without raising an error visible to existing alarms. This is a classic "data dark failure" — infrastructure appeared healthy while the data layer silently dropped 100% of records.

**Why no alert fired:**

The existing CloudWatch alarm on Snowflake row load was configured with a threshold too high for a 20-minute window (likely `< 1000 rows per hour`). Since the failure window was only 4 minutes (02:11–02:15) before the rollback, the per-hour metric never crossed the threshold. Additionally, no alarm existed specifically for Lambda version changes — a version deploy at 2 AM was invisible to the on-call team. The Firehose delivery success metric remained green throughout because Firehose was doing its job: delivering files to S3 correctly. The failure was purely downstream in the Snowflake COPY INTO layer.

**Time taken to find this:** 47 minutes

---

**Signals you connected:**

1. S3 files present in `raw/` with expected timestamps — Firehose healthy, Kinesis healthy.
2. Snowflake `SIGMA.SILVER.TRANSACTIONS` shows zero new rows after 02:11 UTC.
3. CloudWatch Lambda Invocations graph shows a version change event at 02:11:07 UTC on `sigma-kinesis-producer`.
4. Inspecting one S3 file from 02:12 showed `merchant_nm` instead of `merchant_name` — schema drift confirmed.
5. `COPY INTO` history in Snowflake showed `files_loaded=14, rows_loaded=0, errors_seen=14` — confirming the schema mismatch rather than a connectivity failure.

**Signal you missed (fill this in Phase 3 after seeing the agent output):**

The agent correlated the exact Lambda version change timestamp (02:11:07) with the Kinesis shard gap and Snowflake row-count zero in a single query pass — something I missed by checking each system in isolation. I also missed checking the `COPY INTO` error detail (`Column 'MERCHANT_NAME' not found in source`) which would have immediately confirmed the field rename without needing to manually diff S3 file schemas.

---

## Phase 3 — Comparison

**What I found (Phase 2 manual):**
- Time taken: 47 minutes
- Root cause found? Yes
- SLA breach identified? Partial (identified the gap but did not quantify GMV by merchant)
- Prevention created? No

**What the agent found (Phase 3):**
- Time taken: 23 seconds
- Root cause found? Yes
- SLA breach identified? Yes
- Prevention created? Yes (3 live alarms)

**What I missed that the agent caught:**

1. **Exact GMV impact by merchant**: The ImpactAgent queried Snowflake and computed ₹4,72,340 total GMV missing, breaking it down by merchant — QuickMart: ₹1,21,450 missing (SLA threshold ₹50K → BREACHED), FuelPlus: ₹87,200 missing (threshold ₹1,00,000 → not breached). I identified the gap existed but did not quantify it or check SLA contracts.
2. **The COPY INTO error detail**: The ForensicsAgent pulled the exact Snowflake error message (`Column 'MERCHANT_NAME' not found`) which is a definitive 5-second confirmation. I took 20 minutes to reach the same conclusion by manual file diffing.
3. **Idempotent recovery**: The RecoveryAgent replayed Kinesis records using `transaction_id` as a MERGE key, safely loading only the 847 missing records without double-counting. I had not planned how to avoid re-loading records that partially loaded.

**Why the agent caught it:**

The agent has direct API access to all three systems (CloudWatch, Kinesis, Snowflake) simultaneously and correlates signals by timestamp in a single reasoning loop. It does not suffer from cognitive tunnel-vision (e.g., assuming Firehose was healthy means the pipeline is healthy). The agent checks the *data layer* (Snowflake COPY INTO history) as a first-class signal, whereas human engineers typically start with infrastructure metrics.

---

## Judgment Questions

**Forensics Agent:**
*The agent found the root cause by correlating Lambda version history with Snowflake query history. What is the one CloudWatch alarm that would have caught this at 02:12 instead of 09:03? Write it as a metric alarm definition.*

Your answer:

The alarm that would have fired at 02:12 is a **Snowflake zero-row-load alarm** based on a custom CloudWatch metric published by the COPY INTO pipeline:

```
Alarm Name:    sigma-snowflake-zero-load
Namespace:     SigmaDataTech/Pipeline
MetricName:    SnowflakeRowsLoaded
Statistic:     Sum
Period:        300 seconds (5 minutes)
EvaluationPeriods: 1
Threshold:     1
ComparisonOperator: LessThanThreshold
TreatMissingData: breaching
AlarmActions:  [arn:aws:sns:us-east-1:273354663620:sigma-alerts]
```

**Rationale**: A 5-minute window that fires as soon as `SnowflakeRowsLoaded < 1` catches the failure at 02:12 UTC — the first COPY INTO cycle after v2 deployed — rather than waiting for a human to check dashboards at 09:03. The key design choice is `TreatMissingData: breaching` so that if the metric is never published (because the pipeline itself crashes), the alarm still fires.

---

**Recovery Agent:**
*The recovery used transaction_id as the idempotency key. What happens if a legitimate duplicate transaction_id exists in the source data? How would you change the deduplication logic?*

Your answer:

If a legitimate duplicate `transaction_id` exists in source data (e.g., a customer retries payment and the upstream system generates the same ID), the `MERGE INTO` on `transaction_id` will silently drop the second record, treating it as a re-delivery rather than a new transaction. This is a **data loss bug masked by the idempotency design**.

**How to fix it:**

1. **Composite idempotency key**: Use `(transaction_id, created_at, amount)` as the merge key. A true retry will have the same amount and timestamp; a legitimate new transaction with a reused ID will have a different timestamp or amount and will be inserted.

2. **Quarantine-first approach**: Before merging, route any record whose `transaction_id` already exists in the target table to the quarantine bucket with reason `potential_duplicate_id`. A human reviews the quarantine daily. This trades false-negative risk (missing real duplicates) for false-positive safety (never silently dropping legitimate transactions).

3. **Upstream fix (preferred)**: Add a globally unique `event_id` (UUID generated at event source) distinct from `transaction_id`. Use `event_id` for pipeline deduplication and `transaction_id` for business-level deduplication. This separates infrastructure concerns from business logic.

For this lab's scope, option 2 (quarantine-first) is the safest because it makes the ambiguity visible rather than silently resolving it in either direction.

---

**Hardening Agent:**
*The sigma-lambda-version-change alarm fires on any Lambda error spike after a version change. Your team deploys 20 Lambda functions per day in prod. Would you keep this alarm? If yes, how do you stop it from spamming? If no, what replaces it?*

Your answer:

**Yes, keep the alarm — but scope it and add suppression logic.**

With 20 deploys per day, an un-scoped version-change alarm fires constantly and trains engineers to ignore it (alarm fatigue). But removing it entirely means losing the signal that caught this incident.

**Changes to stop spam:**

1. **Scope to data-path Lambdas only**: Apply the alarm only to Lambdas that write to Snowflake or read from Kinesis (e.g., `sigma-kinesis-producer`, `sigma-firehose-transformer`). Internal admin or reporting Lambdas are excluded. This reduces 20 daily triggers to 3–4.

2. **Pair with a data-layer metric**: Change the alarm condition from "Lambda error spike after version change" to "Lambda version change AND Snowflake rows loaded drops below baseline in the next 5 minutes." This makes it a compound alarm that only fires when a version change actually causes downstream data impact — not just any error.

3. **Deployment-time suppression window**: During planned deploys, the CI/CD pipeline calls `SetAlarmState` to put the alarm in `INSUFFICIENT_DATA` for a 10-minute burn-in window. If the pipeline is still healthy after 10 minutes, the alarm resets. If not, it fires.

4. **Replace generic error-spike with a canary pattern**: Route 5% of Kinesis traffic to the new Lambda version for 3 minutes before flipping the `LIVE` alias. If the canary Snowflake load rate drops below 95%, abort the deploy automatically. This catches the failure before it reaches prod scale and eliminates the need for the alarm entirely in the happy path.

**Conclusion**: Keep the alarm, but make it a compound signal and automate the canary gate — so it only fires when it genuinely matters.

---

## Your Honest Reflection

**Which part of the manual investigation took longest and why:**

Connecting the S3 delivery success to the Snowflake load failure took the longest — approximately 25 minutes. The instinct when S3 files are present and Firehose shows no errors is to conclude the pipeline is healthy and look elsewhere (Kinesis, Lambda execution errors, network). The Snowflake COPY INTO history is three clicks deep in the Snowsight UI and not part of a standard first-response runbook. Without a Snowflake query habit built into the incident response process, this signal is invisible under time pressure.

**What would have happened if this hit prod at 2 AM with no agents:**

The failure would have been undetected until the business opened at 09:00 IST (the first time a human refreshed the GMV dashboard). By then, 7 hours of transaction data — potentially 20,000–30,000 records at full production throughput — would be permanently missing from the silver layer. Kinesis retains records for only 24 hours by default, so recovery would still have been possible but would require a senior engineer to manually write and execute a Kinesis replay script under time pressure, with no deduplication safety net. The QuickMart SLA breach would trigger a contractual penalty. Depending on whether the Snowflake Streams feeding downstream analytics consumed the gap, the corruption could propagate into BI dashboards, ML feature stores, and financial reconciliation reports — each requiring separate remediation. A 2 AM silent failure with no agents is a 4-hour P0 incident, a contractual breach, and likely a post-mortem with the CTO.

**One thing you would add to this platform that none of the 6 agents currently do:**

A **Schema Drift Detection Agent** that runs as a standing Kinesis consumer (not triggered by an incident). Every 5 minutes it samples 10 records from the stream, compares the field names and data types against the Snowflake target schema stored in a registry, and fires an SNS alert the moment a field name disappears or a type changes. This agent would have caught `merchant_name → merchant_nm` at 02:11:09 UTC — 23 seconds after v2 deployed — rather than waiting for the COPY INTO failure at 02:12:00 UTC. It operates entirely in the prevention layer, making the Forensics and Recovery agents unnecessary for this class of failure.

---

*Push this file to your team fork before the Phase 2 checkpoint.*
*Incomplete answers are flagged by validate_day12.py*
