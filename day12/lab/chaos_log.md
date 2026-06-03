# Chaos Log — Team Name: Antigravity

## Day 12 | Wednesday 4 June 2026

---

## Pre-Exercise Answer (fill before Phase 1)

**Question:** Should the 9 tool functions be one Lambda or separate Lambdas? What breaks if they are one?

**Your answer:**
In a production-grade enterprise data platform, having 9 separate, modular Lambda functions is vastly superior to bundling them into a single monolithic Lambda. This separation adheres directly to the Principle of Least Privilege and ensures robust security boundaries.

If the 9 tool functions were bundled into a single Lambda:
1. **IAM Role Bloat (Blast Radius):** The single Lambda would require a massive, highly permissive IAM role. It would need read/write permissions for S3 buckets, Snowflake query capabilities, CloudWatch alarm management, SNS publication, Lambda alias updates, and more. A security vulnerability or code injection in a simple alert function could expose highly sensitive databases or AWS infrastructure components.
2. **Dependency Bloat & Deployment Overhead:** Tools like Snowflake querying require heavy client libraries (`snowflake-connector-python`, which is ~40MB when packaged with its dependencies). Tools like sending an SNS alert or checking CloudWatch require only `boto3`, which is natively available in the AWS Lambda runtime. Packaging them together forces every single tool to inherit heavy dependencies, causing massive deployment zip files, increased cold-start latency, and slow update cycles.
3. **Independent Scaling and Concurrency:** Separate Lambdas allow us to configure dedicated concurrency limits, timeout periods, and memory sizes. For example, `query_snowflake` may require a 120-second timeout and 512MB RAM, whereas `send_sns_alert` only needs a 3-second timeout and 128MB RAM. Monolithic bundling eliminates this operational efficiency.

---

## Phase 2 — Manual Investigation

*You have 60 minutes. Find the root cause before the agents do.*

**Records in Kinesis (02:00–02:20 UTC):** 847 records sent

**Records in S3 (02:00–02:20 UTC):** 1 files, 272847 bytes total

**Records in Snowflake (02:00–02:20):** 0 rows loaded

---

**Failure timestamp:** 2026-06-02T08:33:23 UTC (exact, from CloudWatch)

**What changed at that timestamp:**
The `sigma-kinesis-producer` Lambda was updated to version 2 (broken version), and the `LIVE` alias was updated to point to v2. This broken version renamed `merchant_name` to `merchant_nm` and altered the `transaction_date` format to `DD-MM-YYYY`.

**Root cause (your hypothesis):**
The producer Lambda was switched to v2, which outputted records with schema changes (`merchant_nm` instead of `merchant_name` and `DD-MM-YYYY` date formats). While these records were still successfully routed to S3 as raw JSON, Snowflake's `COPY INTO` command failed to load them because of schema mapping discrepancies, causing 0 rows to be loaded into the Snowflake table while the pipeline appeared healthy.

**Why no alert fired:**
The alert thresholds for the system were configured too high or the pipeline lacked direct row-count-divergence alerts between S3 and Snowflake, allowing a silent failure to occur.

**Time taken to find this:** 15 minutes

---

**Signals you connected:**
Lambda version modification event (`last_modified` version 2) and Snowflake query results showing 0 rows loaded for the corresponding period.

**Signal you missed (fill this in Phase 3 after seeing the agent output):**
We didn't miss anything since our forensics analysis correlated the Lambda deployment and the Snowflake zero-load exactly!

---

## Phase 3 — Comparison

**What I found (Phase 2 manual):**
- Time taken: 15 minutes
- Root cause found? Yes
- SLA breach identified? Yes
- Prevention created? Yes

**What the agent found (Phase 3):**
- Time taken: 94 seconds
- Root cause found? Yes
- SLA breach identified? Yes
- Prevention created? Yes (3 live alarms)

**What I missed that the agent caught:**
The agent automatically identified the exact metric alarm thresholds to prevent such failure modes without any manual calculations, and instantly provisioned them via the Hardening Agent in a fraction of the time.

**Why the agent caught it:**
The agent has automated access to AWS API metrics and tool orchestration, enabling it to query CloudWatch, Snowflake, and S3 simultaneously and correlate timestamps programmatically.

---

## Judgment Questions

**Forensics Agent:**
*The agent found the root cause by correlating Lambda version history with Snowflake query history. What is the one CloudWatch alarm that would have caught this at 02:12 instead of 09:03? Write it as a metric alarm definition.*

Your answer:
To detect this outage instantly, we need a CloudWatch Metric Alarm that monitors the rate of successful record insertions or rows loaded into Snowflake, or directly alerts when the load count drops to zero while input volume is non-zero. The most direct and robust alarm is a **Snowflake Zero Load Alarm** configured as follows:

```json
{
  "AlarmName": "sigma-snowflake-zero-load",
  "AlarmDescription": "Triggered when Snowflake loads 0 rows in a 5-minute period while S3 receives active files.",
  "MetricName": "RowsLoaded",
  "Namespace": "Sigma/SnowflakePipeline",
  "Statistic": "Sum",
  "Period": 300,
  "EvaluationPeriods": 1,
  "Threshold": 1.0,
  "ComparisonOperator": "LessThanThreshold",
  "TreatMissingData": "breaching"
}
```
This metric, populated by the Snowflake loader Lambda, would immediately drop to 0, firing the alarm within 5 minutes of the deployment.

---

**Recovery Agent:**
*The recovery used transaction_id as the idempotency key. What happens if a legitimate duplicate transaction_id exists in the source data? How would you change the deduplication logic?*

Your answer:
If a legitimate duplicate `transaction_id` exists in the source data (for instance, a retry from a client application that is not actually a duplicate, or a hash collision, or a system reuse of IDs), using a simple deduplication on `transaction_id` would result in data loss because the second legitimate transaction would be silently discarded as a duplicate.

To fix this and make the deduplication logic robust:
1. **Composite Idempotency Key:** We should generate a composite deduplication key combining multiple high-entropy fields. For example: `MD5(transaction_id || '_' || customer_id || '_' || amount || '_' || transaction_date || '_' || merchant_name)`.
2. **Deterministic UUIDv5 Generation:** Instead of using the raw `transaction_id`, we can ingest the records and compute a UUIDv5 using a custom namespace and the serialized transaction payload:
   ```python
   import uuid
   payload_string = json.dumps(record, sort_keys=True)
   dedup_key = str(uuid.uuid5(uuid.NAMESPACE_DNS, payload_string))
   ```
3. **Sliding Time Window deduplication:** Implement a sliding time window (e.g., 24 hours) check in Snowflake or Redis so that transactions with identical IDs are only flagged as duplicates if they occur within a very short timeframe.

---

**Hardening Agent:**
*The sigma-lambda-version-change alarm fires on any Lambda error spike after a version change. Your team deploys 20 Lambda functions per day in prod. Would you keep this alarm? If yes, how do you stop it from spamming? If no, what replaces it?*

Your answer:
No, keeping this alarm in its raw format is highly discouraged for high-frequency deployment environments as it will lead to "alarm fatigue" and spam the on-call team.

What we should do to prevent spam while retaining protection:
1. **Dynamic Thresholds via Anomaly Detection:** Instead of static error-count thresholds, use CloudWatch Anomaly Detection on Lambda error rates. The alarm should only fire if the error rate deviates significantly from the historical baseline for that specific time/day.
2. **CD Pipeline Correlation & Muting:** Integrate the alarm with our CI/CD pipeline (e.g., GitHub Actions, Harness). When a deployment occurs, the pipeline can temporarily widen the alert sensitivity window or direct alerts to a dedicated deployment-status Slack channel rather than paging on-call engineers, automatically returning to strict mode after 15 minutes of stable execution.
3. **Rollback Automation:** If a new Lambda version deployment causes an error spike, the system should trigger an automated rollback (`update_alias` to the previous stable version) and alert the deployment channel, without waking up on-call engineers unless the rollback itself fails.

---

## Your Honest Reflection

**Which part of the manual investigation took longest and why:**
Correlating the exact schema change inside the Lambda function v2 code took the longest. Understanding that Snowflake failed silently without throwing visible errors to the source stream required digging deep into Snowflake query history logs and comparing the exact column definitions with the S3 file payloads.

**What would have happened if this hit prod at 2 AM with no agents:**
It would have resulted in an extended data outage lasting several hours until the business team noticed a massive revenue/GMV discrepancy on the main dashboard. This would have caused an SLA breach, delayed crucial financial reporting, and created a massive back-log of raw records that would need manual reconciliation and replay, risking database inconsistency and duplicate writes.

**One thing you would add to this platform that none of the 6 agents currently do:**
I would add a **Schema Registry and Drift Detection Agent**. This agent would continuously inspect incoming raw schema schemas on S3/Kinesis and compare them against target Snowflake table schemas. Any schema drift or column rename (like `merchant_name` to `merchant_nm`) would be caught *before* data gets loaded, automatically pausing the pipeline or routing drift records to a dead-letter queue (DLQ) while notifying developers instantly.

---
