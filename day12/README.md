# Day 13 — The Sigma Intelligence Platform
## End-to-End Industry Production Pipeline + Agentic AI

**Wednesday 4 June 2026 | 11 AM – 4 PM**

> You have spent 12 days building individual components — SQL agents, pipeline generators,
> quality checkers, PII detectors, self-heal loops.
>
> Today you wire everything into one production-grade platform.
> The same stack that runs at PhonePe, Razorpay, and CRED.
> You will build it, break it, fix it manually, and then watch AI fix it automatically.
>
> By 4 PM you will have something worth putting on your resume.

---

## The Situation

**Sigma DataTech** (Series B fintech, 4M transactions/day) has promoted you.

You are no longer a junior DE running scripts. You are the **Platform Engineering team** —
responsible for the full data pipeline from merchant transactions to business dashboards.

Your CTO has one requirement:

> *"I want to know about data problems BEFORE the business does.
> Not after the dashboard breaks. Not after compliance calls.
> Before."*

That is what you are building today.

---

## What You Are Building

```
[Lambda Data Generator]
        ↓  PutRecord (1000 tx/min)
[Kinesis Data Streams]
        ↓
[Kinesis Firehose]  ──────────────→  S3 Bronze  (raw, partitioned by date)
                                           ↓
                                   Databricks Autoloader
                                           ↓
                                    Delta Lake Bronze
                                           ↓
                                    Delta Lake Silver  (cleaned, typed)
                                           ↓
                                       dbt models
                                           ↓
                                    Delta Lake Gold   (aggregated)
                                           ↓
                                      Snowflake       (warehouse)
                                           ↓
                                     Dashboards

AGENTS (wired in Phase 3):
  Schema Evolution Agent  ←  detects drift at S3 Bronze
  PII Detection Agent     ←  scans before Silver load
  Ingestion Quality Agent ←  GE rules + quarantine + load decision
```

---

## Team Setup

- Teams of 4 — same teams as all week
- One GitHub fork per team — push all outputs there
- One shared AWS account per team (your existing credentials)
- Databricks trial workspace — already connected to S3
- Snowflake trial — already set up from earlier sessions

---

## Prerequisites (confirm before 11 AM)

```bash
# Confirm AWS credentials work
aws sts get-caller-identity

# Confirm Kinesis access
aws kinesis list-streams --region us-east-1

# Confirm S3 bucket exists (create if not)
aws s3 ls s3://sigma-datatech-<your-team-name>/

# Confirm Snowflake connection (run in Snowflake UI)
SELECT CURRENT_USER(), CURRENT_WAREHOUSE(), CURRENT_DATABASE();

# Confirm Python packages
pip install boto3 pandas great_expectations faker --break-system-packages -q
```

**If any of these fail — fix before 11 AM. Do not start Phase 1 with broken credentials.**

---

---

# PHASE 1 — BUILD IT CLEAN
## 11:00 AM – 12:00 PM

> Goal: Full pipeline running. Snowflake Gold table has data. One hour. Go.

---

### Step 1 — Create Kinesis Data Stream

```bash
aws kinesis create-stream \
  --stream-name sigma-transactions \
  --shard-count 1 \
  --region us-east-1
```

Wait 30 seconds, confirm:
```bash
aws kinesis describe-stream-summary \
  --stream-name sigma-transactions \
  --region us-east-1 \
  --query 'StreamDescriptionSummary.StreamStatus'
```
Expected output: `"ACTIVE"`

---

### Step 2 — Create Kinesis Firehose → S3

```bash
# First create the S3 bucket (replace <your-team-name>)
aws s3 mb s3://sigma-datatech-<your-team-name> --region us-east-1

# Create Firehose delivery stream
aws firehose create-delivery-stream \
  --delivery-stream-name sigma-firehose \
  --delivery-stream-type KinesisStreamAsSource \
  --kinesis-stream-source-configuration \
    KinesisStreamARN=arn:aws:kinesis:us-east-1:<account-id>:stream/sigma-transactions,\
    RoleARN=arn:aws:iam::<account-id>:role/firehose-role \
  --s3-destination-configuration \
    RoleARN=arn:aws:iam::<account-id>:role/firehose-role,\
    BucketARN=arn:aws:s3:::sigma-datatech-<your-team-name>,\
    Prefix=bronze/transactions/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/,\
    CompressionFormat=GZIP \
  --region us-east-1
```

> **Note:** Use the IAM role from your team's AWS account. If the role does not exist, create it with `AmazonKinesisFirehoseFullAccess` and `AmazonS3FullAccess` policies.

---

### Step 3 — Start the Data Generator

```bash
python lab/data_generator.py --mode clean --records 500 --stream sigma-transactions
```

Watch the output:
```
[11:03:42] Sent record TXN100001 | merchant: QuickMart | amount: 4521.50 | currency: INR
[11:03:42] Sent record TXN100002 | merchant: FuelPlus  | amount: 892.00  | currency: INR
...
[11:03:55] 500 records sent to Kinesis sigma-transactions
```

Confirm records in Kinesis:
```bash
aws kinesis get-shard-iterator \
  --stream-name sigma-transactions \
  --shard-id shardId-000000000000 \
  --shard-iterator-type TRIM_HORIZON \
  --region us-east-1
```

Wait 60–90 seconds for Firehose to deliver to S3:
```bash
aws s3 ls s3://sigma-datatech-<your-team-name>/bronze/ --recursive
```
You should see `.gz` files. If empty, wait another 60 seconds.

---

### Step 4 — Databricks: Bronze → Silver → Gold

Open your Databricks workspace. Create a new notebook: `sigma_pipeline_day13`.

**Bronze — read from S3 with Autoloader:**
```python
bronze_df = (spark.readStream
  .format("cloudFiles")
  .option("cloudFiles.format", "json")
  .option("cloudFiles.schemaLocation", "/mnt/sigma/bronze/_schema")
  .load("s3://sigma-datatech-<your-team-name>/bronze/transactions/"))

bronze_df.writeStream \
  .format("delta") \
  .outputMode("append") \
  .option("checkpointLocation", "/mnt/sigma/bronze/_checkpoint") \
  .toTable("sigma.bronze.transactions")
```

**Silver — clean and type-cast:**
```python
from pyspark.sql.functions import col, to_date, when

silver_df = spark.table("sigma.bronze.transactions") \
  .filter(col("transaction_id").isNotNull()) \
  .filter(col("amount").cast("double") > 0) \
  .withColumn("transaction_date", to_date(col("transaction_date"), "yyyy-MM-dd")) \
  .withColumn("amount", col("amount").cast("double"))

silver_df.write.format("delta").mode("overwrite").saveAsTable("sigma.silver.transactions")
```

**Gold — aggregate:**
```python
gold_df = spark.table("sigma.silver.transactions") \
  .groupBy("merchant_name", "category", "transaction_date") \
  .agg({"amount": "sum", "transaction_id": "count"}) \
  .withColumnRenamed("sum(amount)", "total_amount") \
  .withColumnRenamed("count(transaction_id)", "transaction_count")

gold_df.write.format("delta").mode("overwrite").saveAsTable("sigma.gold.merchant_daily")
```

---

### Step 5 — dbt: Load Gold to Snowflake

In your dbt project directory:
```bash
cd sigma_dbt
dbt run --select merchant_daily
dbt test --select merchant_daily
```

Expected:
```
Running 1 model...  merchant_daily  [OK in 3.45s]
Running 2 tests...  [PASS] [PASS]
```

Confirm in Snowflake:
```sql
SELECT merchant_name, SUM(total_amount) as gmv
FROM SIGMA.GOLD.MERCHANT_DAILY
GROUP BY merchant_name
ORDER BY gmv DESC
LIMIT 5;
```

---

### ✅ PHASE 1 CHECKPOINT — 12:00 PM SHARP

Every team shows Anil:
1. Snowflake query result — Gold table has data (row count on screen)
2. S3 Bronze files exist (one `aws s3 ls` command)
3. dbt test output — all green

**No data in Snowflake = not done. Stay behind. Others move to Phase 2.**

---

---

# PHASE 2 — CHAOS HOUR
## 12:00 PM – 1:00 PM

> Anil injects 3 pain points at 12:00 PM sharp.
> Your job: find what broke, fix it manually, explain it.
> No agents yet. No AI shortcuts. Your hands.

---

### Injection 1 — Schema Drift (12:00 PM)

Anil runs on his machine:
```bash
python lab/data_generator.py --mode chaos --inject schema_drift --records 200
```

The new feed adds 2 new columns (`upi_ref_id`, `device_fingerprint`) and renames
`merchant_name` to `merchant_nm`.

**What breaks:** Databricks Silver query fails. Downstream dbt model fails.
`merchant_daily` in Snowflake stops updating.

**Your job — manual fix:**
1. Identify which column changed (check the error message — read it properly)
2. Update the Silver transformation to handle both old and new column names
3. Re-run the Silver notebook
4. Re-run `dbt run`
5. Confirm Snowflake is updating again

**Proof required:**
Write in your team's `chaos_log.md`:
```
INJECTION 1 — Schema Drift
What broke: [your answer]
Where exactly in the pipeline: [Bronze / Silver / Gold / dbt / Snowflake]
Root cause: [one sentence]
Fix applied: [what you changed]
Time to fix: [HH:MM]
```

---

### Injection 2 — PII Leak (12:20 PM)

Anil runs:
```bash
python lab/data_generator.py --mode chaos --inject pii_leak --records 200
```

A new merchant source starts sending `cust_ph`, `acct_no`, `emp_pncd` in plain text
inside the transaction payload. These are phone numbers, bank account numbers, and PIN codes.

**What breaks:** Nothing breaks visibly. Pipeline runs fine. Data loads to Snowflake.
**That is the problem.** PII is sitting in your Gold table unmasked.

**Your job — manual fix:**
1. Find which columns contain PII (look at the raw S3 Bronze files)
2. Add masking in the Silver transformation (hash or redact)
3. Re-run Silver and Gold
4. Confirm the masked values in Snowflake

**Proof required:**
```
INJECTION 2 — PII Leak
Columns found: [list them]
How you found them: [column name scan / sample value check / other]
Masking applied: [what method]
Missed any? [be honest]
Why regex alone would not catch cust_ph: [one sentence]
```

---

### Injection 3 — Data Quality Rot (12:40 PM)

Anil runs:
```bash
python lab/data_generator.py --mode chaos --inject quality_rot --records 300
```

300 records arrive with:
- 18 blank `transaction_id` values (null primary keys)
- 12 negative `amount` values
- 7 records with `transaction_date` = `99-99-9999`
- 4 records with `currency` = `XYZ`

**What breaks:** Silver loads dirty data. Gold aggregations are wrong.
Snowflake dashboard shows negative GMV for 3 merchants.

**Your job — manual fix:**
1. Add filters in Silver to catch and remove/flag bad records
2. Count how many records were dropped (you must know this number)
3. Re-run Silver → Gold → dbt
4. Confirm Snowflake GMV is positive again

**Proof required:**
```
INJECTION 3 — Data Quality Rot
Records received: 300
Records dropped: [your count]
Records loaded to Silver: [your count]
Filters added: [list the 4 conditions]
Why this matters for a fintech business: [one sentence]
```

---

### ✅ PHASE 2 CHECKPOINT — 1:00 PM

Before lunch, Anil cold-calls **one member per team** (Wheel of Names).

No laptop. No notes. Answer live:

- "Tell me exactly what schema drift is and where it hit your pipeline."
- "Your PII was in `cust_ph`. How did you find it? What did you do with it?"
- "How many records did you drop in Injection 3? Why that number?"

**Wrong answer = your team's chaos_log.md is marked incomplete.**

Save `chaos_log.md` to your team's repo before going to lunch.

---

---

# PHASE 3 — AGENTS TO THE RESCUE
## 2:00 PM – 4:00 PM

> You just spent an hour doing manually what takes 90 seconds with an agent.
> Now wire in the agents. Run the same chaos. Watch the difference.

---

### Agent 1 — Schema Evolution Agent (2:00 – 2:35 PM)

**What it does:** Detects schema changes at S3 Bronze, compares to last known schema,
generates the ALTER TABLE SQL, applies it, alerts via log.

**Wire it in:**

```bash
python lab/agents/schema_evolution_agent.py \
  --bucket sigma-datatech-<your-team-name> \
  --prefix bronze/transactions/ \
  --baseline-table sigma.silver.transactions
```

Now trigger Injection 1 again:
```bash
python lab/data_generator.py --mode chaos --inject schema_drift --records 100
```

Watch the agent output:
```
[14:08:12] New file detected: bronze/transactions/.../part-001.gz
[14:08:13] Schema comparison: 2 new columns, 1 renamed column
[14:08:14] Generated ALTER TABLE: ADD COLUMN upi_ref_id STRING
[14:08:14] Generated column mapping: merchant_nm → merchant_name
[14:08:15] Silver table updated. Pipeline resumed.
[14:08:15] Incident logged: schema_drift_incident_001.json
```

**Proof:** `agent_outputs/schema_drift_incident_001.json` in your repo.

**Judgment question — answer in the JSON:**
> "The agent added a nullable column automatically. Two downstream analysts
> use merchant_name in their reports. What could go wrong and what guardrail would you add?"

---

### Agent 2 — PII Detection Agent (2:35 – 3:10 PM)

**What it does:** Scans every new S3 file before it enters Databricks.
Regex for known PII patterns. LLM for abbreviated column names.
Blocks load if Restricted tier. Masks if Confidential tier.

**Wire it in:**

```bash
python lab/agents/pii_detection_agent.py \
  --bucket sigma-datatech-<your-team-name> \
  --prefix bronze/transactions/ \
  --action mask_and_continue
```

Now trigger Injection 2 again:
```bash
python lab/data_generator.py --mode chaos --inject pii_leak --records 100
```

Watch the agent output:
```
[14:38:22] Scanning: bronze/transactions/.../part-002.gz
[14:38:23] Regex scan: 0 confirmed PII columns
[14:38:24] LLM scan: cust_ph → phone_number (CONFIDENTIAL)
[14:38:24] LLM scan: acct_no → account_number (RESTRICTED)
[14:38:24] LLM scan: emp_pncd → pin_code (CONFIDENTIAL)
[14:38:25] Action: masking cust_ph, emp_pncd | BLOCKING load for acct_no
[14:38:25] Sensitivity report: pii_scan_002.json
```

**Proof:** `agent_outputs/pii_scan_002.json` in your repo.

**Judgment question:**
> "The regex found ZERO PII. The LLM found THREE. When would you skip the LLM scan
> to save cost? What is the risk of skipping it?"

---

### Agent 3 — Ingestion Quality Agent (3:10 – 3:45 PM)

**What it does:** Profiles new data → generates GE expectations via LLM →
runs checks → auto-fixes safe issues → quarantines bad rows → generates load decision.

**Wire it in:**

```bash
python lab/agents/ingestion_quality_agent.py \
  --bucket sigma-datatech-<your-team-name> \
  --prefix bronze/transactions/ \
  --snowflake-table SIGMA.SILVER.TRANSACTIONS
```

Now trigger Injection 3 again:
```bash
python lab/data_generator.py --mode chaos --inject quality_rot --records 300
```

Watch the agent output:
```
[15:12:01] Profiling 300 new records...
[15:12:03] Generated 11 GE expectations from profile
[15:12:04] Running quality checks...
[15:12:05] CRITICAL FAIL: 18 null transaction_ids → quarantined
[15:12:05] HIGH FAIL: 12 negative amounts → quarantined
[15:12:05] HIGH FAIL: 7 invalid dates → marked INVALID_DATE
[15:12:05] MEDIUM FAIL: 4 unknown currencies → quarantined
[15:12:06] Auto-fix: whitespace stripped from all string columns
[15:12:06] Load decision: quarantine_and_load
[15:12:06] Clean rows: 259 → loading to Snowflake
[15:12:06] Quarantined: 41 rows → quarantine.csv
[15:12:07] Quality report: quality_report_003.json
```

**Proof:** `agent_outputs/quality_report_003.json` + `agent_outputs/quarantine_003.csv` in your repo.

**Judgment question:**
> "The agent loaded 259 rows and quarantined 41. Your business analyst
> says GMV is down 14% today. Is that because of the quarantine? How do you check?"

---

### 🎯 WOW MOMENT — 3:45 PM

All 3 agents running simultaneously.

Anil triggers all 3 injections at once:
```bash
python lab/data_generator.py --mode chaos --inject all --records 500
```

Your pipeline receives 500 dirty, schema-drifted, PII-leaking records.

All 3 agents fire:
- Schema Evolution Agent catches the drift → auto-applies mapping
- PII Agent catches `cust_ph`, `acct_no` → masks before load
- Quality Agent profiles → generates rules → quarantines 50 bad rows → loads 450 clean

Snowflake Gold table updates. Clean. Correct. Masked. Documented.

**Time from Kinesis PUT to Snowflake Gold: under 5 minutes. Zero manual intervention.**

---

### ✅ PHASE 3 CHECKPOINT — 4:00 PM

Run the validator:
```bash
python tests/validate_day13.py
```

Push to your fork:
```bash
git add .
git commit -m "Day 13 complete - full agentic pipeline"
git push
```

Anil checks all 9 teams via `check_submissions.py`.

**Required output files per team:**
- `chaos_log.md` — manual fix evidence
- `agent_outputs/schema_drift_incident_*.json`
- `agent_outputs/pii_scan_*.json`
- `agent_outputs/quality_report_*.json`
- `agent_outputs/quarantine_*.csv`

---

---

# THE 12-MINUTE Q&A — 4:00 PM

One question per team. Verbal. No laptop. Wheel of Names picks who answers.

Anil's questions (one per team, randomly assigned):

1. "Your schema agent added a nullable column. Downstream dbt model now shows NULLs. Who is responsible — the agent or the engineer who approved it?"
2. "Your PII agent masked `acct_no`. Three weeks later compliance asks for the original value for an audit. Can you recover it? Should you be able to?"
3. "Your quality agent quarantined 41 rows. The on-call analyst calls — revenue is down. What is your first action?"
4. "Your self-heal agent fixed the pipeline by dropping 12 rows. Pipeline is green. No alert fired. What is the hidden problem?"
5. "Kinesis is down. Your agents are waiting for S3 events that never come. How does your pipeline fail — loudly or silently?"
6. "You have 9 agents running in Docker. One crashes at 3 AM. How does the pipeline know? How does it recover?"
7. "Your dbt test catches a null in merchant_name. 2000 rows affected. Do you quarantine all 2000 or load with NULLs and flag them?"
8. "The LLM in your PII agent hallucinated — it said `city` is a PII column. It masked all city values. Business dashboard now shows blank cities. How do you prevent this?"
9. "Your pipeline processes 500 records/minute cleanly. Tomorrow a new merchant sends 50,000 records/minute. What breaks first?"

---

---

# WHAT YOU BUILT TODAY

```
Industry Stack:
  AWS Kinesis + Firehose → S3 (data lake)
  Databricks Autoloader + Delta Lake (Bronze / Silver / Gold)
  dbt (transformation + testing)
  Snowflake (warehouse)

Agentic AI Layer:
  Schema Evolution Agent  (drift detection + auto-remediation)
  PII Detection Agent     (regex + LLM + masking + compliance report)
  Ingestion Quality Agent (profile + GE rules + quarantine + load decision)

Production Patterns:
  Event-driven architecture (S3 event → agent trigger)
  Quarantine pattern (bad rows separated, not silently dropped)
  Audit trail (every agent action logged and versioned)
  Human-in-the-loop checkpoint (judgment question in every agent output)
```

This is not a classroom exercise. This is a production pattern.
The same architecture runs at every serious fintech in India.

You now know how to build it, break it, and make it heal itself.

---

*Sigma DataTech · Day 13 · The Platform Is Alive*
