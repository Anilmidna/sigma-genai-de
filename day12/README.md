# Day 12 — The Sigma Intelligence Platform
## 7-Agent Self-Healing Production Pipeline on AWS Bedrock

**Wednesday 4 June 2026 | 11 AM – 4 PM**

> You have spent 11 days building individual AI components —
> SQL agents, pipeline generators, quality checkers, PII detectors.
>
> Today you wire everything into one production-grade platform
> with a 7-agent AI system that investigates, diagnoses, and heals
> a broken pipeline — autonomously, in under 90 seconds.
>
> The same architecture pattern runs at PhonePe, Razorpay, and CRED.
> You will build it, break it, and watch AI fix it without human intervention.
>
> By 4 PM you will have something worth talking about in any interview.

---

## The Situation

**It is 9:03 AM at Sigma DataTech.**

Your analytics manager opens the daily dashboard — the one the sales team uses every morning to check yesterday's numbers.

She sends you a message:

> *"Something is wrong. Yesterday we had 1,20,000 transactions on the dashboard.
> Today it's showing only 40,000 — and it's already 9 AM.
> The pipeline shows green everywhere. What happened to the other 80,000 records?"*

You check. Lambda is green. Kinesis is green. Firehose is green.
S3 has files. Everything looks healthy. Nothing is alerting.

The pipeline ran all night. It sent data. Files arrived in S3.
And somehow **80,000 records never reached Snowflake — never reached the dashboard.**

This is the worst kind of production failure — **the silent one.**
The system did not crash. It did not raise an error. It ran perfectly. And produced the wrong output.

Someone made a business decision this morning based on those 40,000 numbers. **They were wrong.**

You have one hour to find what broke before the agents take over.

---

## What You Are Building

```
[Data Generator / Kinesis Producer Lambda]
          ↓  PutRecord
[Kinesis Data Stream: sigma-transactions]
          ↓
[Kinesis Firehose]
          ↓
[S3 Bronze: sigma-datatech-<team>/bronze/]
          ↓
[S3 ObjectCreated Event]
          ↓
[EventBridge Rule]
          ↓
[Lambda: pipeline_trigger.py]
   calls Bedrock Supervisor Agent
          ↓
┌─────────────────────────────────────────────────────────┐
│              BEDROCK SUPERVISOR AGENT                   │
│         Amazon Nova Pro + Bedrock Guardrails            │
│   "GMV ₹0 since 2AM. Pipeline healthy. Investigate."   │
│                                                         │
│  discovers tools via ──→  [MCP SERVER (Lambda)]        │
│  queries history via  ──→  [BEDROCK KNOWLEDGE BASE]    │
│                                                         │
│  delegates to 6 specialist sub-agents:                 │
│                                                         │
│  [FORENSICS]  [IMPACT]  [RECOVERY]                     │
│  [ROLLBACK]   [HARDENING]  [INCIDENT REPORT]           │
└────────────────────────┬────────────────────────────────┘
                         ↓
         [LAMBDA TOOL FUNCTIONS — 9 tools]
         check_cloudwatch  |  get_kinesis_records
         query_snowflake   |  rollback_lambda_version
         create_alarm      |  quarantine_rows
         load_snowflake    |  write_incident_report
         send_sns_alert
                         ↓
┌────────────────────────────────────────────────────────┐
│  RESULTS                                               │
│  Snowflake: ₹4.69L GMV restored                       │
│  S3: incident_report_20260604.md (CTO-ready)          │
│  CloudWatch: 3 new alarms created (live in account)   │
│  SNS: alert sent → your phone                         │
│  Lambda: rolled back to stable version                 │
└────────────────────────────────────────────────────────┘
```

---

## The 7 Agents

| Agent | Role | What makes it extraordinary |
|---|---|---|
| **Supervisor** | Orchestrates all 6 sub-agents. Re-routes when findings are unexpected. | Reasons across all findings. Does not just collect — decides. |
| **Forensics** | Correlates CloudWatch + Kinesis + S3 + Snowflake across a timeline. | Finds the 4-minute failure window. Identifies Lambda v2 as root cause. |
| **Impact** | Calculates exact GMV loss. Checks SLA contracts. Confirms breach. | ₹4,72,340 missing. QuickMart threshold ₹50K. Breach confirmed. |
| **Recovery** | Gets Kinesis shard iterator at failure timestamp. Replays missed records idempotently. | 824 loaded, 23 quarantined. No duplicates. Snowflake row count verified. |
| **Rollback** | Identifies bad Lambda version. Rolls back via API. Sends test records. | Lambda v2 → v1 in 8 seconds. Verified with 5 live test records. |
| **Hardening** | Creates 3 new CloudWatch alarms. They exist in your account after this run. | Not recommendations — actual alarms. Live. Right now. |
| **Incident Report** | Compiles all findings into a CTO-ready post-mortem. Writes to S3. | Timeline, root cause, business impact, fix applied, prevention added. |

---

## The Three AI Layers

### Bedrock Multi-Agent Collaboration
The supervisor and 6 sub-agents run entirely inside AWS Bedrock.
No servers. No Docker. No EC2 for the agents.
You configure them — AWS runs them.

### MCP Server (Model Context Protocol)
The 9 Lambda tool functions are exposed as an MCP server.
Agents discover tools at runtime — not hardcoded.
Add a new tool tomorrow → every agent uses it immediately.
No agent code changes needed.

### Bedrock Knowledge Base (RAG)
Four document collections in a Bedrock Knowledge Base:
- `past_incidents/` — every incident report from previous runs
- `sla_contracts/` — QuickMart, FuelPlus, TechZone SLA PDFs
- `runbooks/` — engineering runbooks for known failure patterns
- `data_contracts/` — expected schema per merchant source

Every agent queries this before acting.
The system gets smarter with every incident.

### Bedrock Guardrails
Sits between every agent and the LLM:
- **PII redaction** — data samples with phone/account numbers → redacted before LLM sees them
- **Destructive ops blocked** — no DROP, DELETE, TRUNCATE in any generated SQL
- **Grounding enforced** — agent responses must cite retrieved data, not hallucinate

This is mandatory for a regulated fintech. Not optional.

---

## What Is Pre-Configured (Trainer Has Done This)

Before 11 AM the following are live in AWS:

| Resource | What it is |
|---|---|
| Bedrock Supervisor Agent | Configured with 6 sub-agents and all action groups |
| 6 Bedrock Sub-Agents | Each with instructions, action groups, Knowledge Base access |
| Bedrock Knowledge Base | Populated with SLA contracts, runbooks, data contracts |
| Bedrock Guardrail | PII filter + topic denial + grounding enabled |
| IAM Role: `sigma-lambda-role` | Permissions for all 9 Lambda tools |
| Kinesis stream: `sigma-transactions` | 1 shard, active |
| S3 bucket: `sigma-datatech-class` | Firehose destination |
| SNS Topic: `sigma-alerts` | Your email subscribed |
| Lambda: `sigma-kinesis-producer` | v1 (stable) and v2 (broken) pre-deployed |
| The Silent Disaster | Injected — pipeline broke at 2 AM, ₹4.7L missing |

**You deploy:** 9 Lambda tool functions.
**You trigger:** The supervisor agent.
**You watch:** Autonomous recovery.
**You extend:** Forensics Agent with one new detection rule.

---

## Prerequisites — Confirm Before 11 AM

```bash
# AWS credentials
aws sts get-caller-identity

# Kinesis stream active
aws kinesis describe-stream-summary \
  --stream-name sigma-transactions \
  --region us-east-1 \
  --query 'StreamDescriptionSummary.StreamStatus'
# Expected: "ACTIVE"

# S3 bucket accessible
aws s3 ls s3://sigma-datatech-<your-team-name>/

# Snowflake connection
# Run in Snowflake UI:
SELECT CURRENT_USER(), CURRENT_WAREHOUSE(), CURRENT_DATABASE();

# Python packages (all dependencies in one command)
pip install -r lab/requirements.txt

# Optional: Langfuse observability — free at https://langfuse.com
# Sign up → create a project → copy Public Key + Secret Key into lab/.env
# Skip this if you don't want the trace dashboard — lab works without it.

# Copy environment file
cp lab/.env.example lab/.env
# Fill in your team values — Anil will give you the Bedrock agent IDs
```

Your `.env` file must have these values before proceeding:

```
AWS_DEFAULT_REGION=us-east-1
SIGMA_S3_BUCKET=sigma-datatech-<your-team-name>
SIGMA_STREAM=sigma-transactions
SUPERVISOR_AGENT_ID=<from Anil>
SUPERVISOR_ALIAS_ID=<from Anil>
GUARDRAIL_ID=<from Anil>
KNOWLEDGE_BASE_ID=<from Anil>
SNOWFLAKE_ACCOUNT=<your account>
SNOWFLAKE_USER=<your user>
SNOWFLAKE_PASSWORD=<your password>
SNOWFLAKE_DATABASE=SIGMA
SNOWFLAKE_WAREHOUSE=SIGMA_WH
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:<account-id>:sigma-alerts
LAMBDA_ROLE_ARN=arn:aws:iam::<account-id>:role/sigma-lambda-role
```

---

---

# PHASE 1 — WIRE THE PLATFORM
## 11:00 AM – 11:45 AM

> Goal: All 9 Lambda tools deployed. Clean data flows from Kinesis to Snowflake.
> Agents are ready. You understand what each tool does before the disaster hits.

---

### Manual-First Exercise — 5 Minutes

Before deploying anything, answer this in your team:

> *"You have a multi-agent system where a Forensics Agent needs to check
> CloudWatch metrics AND query Snowflake AND read S3 files.
> Should these be one Lambda function or three separate ones?
> What breaks if they are one? What breaks if they are three?"*

Write your answer in `chaos_log.md` under **Pre-Exercise Answer**.
You will revisit this after Phase 3.

---

### Step 1 — Understand the Tool Functions

Read each file in `lab/tools/` before deploying. Every file is 30–50 lines.
For each one, answer: *what AWS service does it call and what does it return?*

```
lab/tools/
  check_cloudwatch.py        → queries CloudWatch metrics API
  get_kinesis_records.py     → gets records from a shard at a specific timestamp
  query_snowflake.py         → runs SQL against Snowflake, returns JSON
  rollback_lambda_version.py → switches Lambda alias to a previous version
  create_cloudwatch_alarm.py → creates a CloudWatch alarm via boto3
  quarantine_rows.py         → writes bad records to S3 quarantine/
  load_to_snowflake.py       → bulk loads clean records to Snowflake
  write_incident_report.py   → writes markdown report to S3 reports/
  send_sns_alert.py          → publishes alert message to SNS topic
```

---

### Step 2 — Deploy All 9 Lambda Tool Functions

```bash
cd day12
bash deploy/deploy_tools.sh
```

Watch the output. Each tool deploys in ~15 seconds:
```
[1/9] Deploying sigma-tool-check-cloudwatch...     OK
[2/9] Deploying sigma-tool-get-kinesis-records...  OK
[3/9] Deploying sigma-tool-query-snowflake...      OK
[4/9] Deploying sigma-tool-rollback-lambda...      OK
[5/9] Deploying sigma-tool-create-alarm...         OK
[6/9] Deploying sigma-tool-quarantine-rows...      OK
[7/9] Deploying sigma-tool-load-snowflake...       OK
[8/9] Deploying sigma-tool-write-report...         OK
[9/9] Deploying sigma-tool-send-alert...           OK

All tools deployed. Testing MCP discovery...
MCP Server found 9 tools. Agent discovery ready.
```

If any tool fails — check the error message, fix the `.env` value it references.

---

### Step 3 — Verify MCP Tool Discovery

```bash
python lab/mcp/test_mcp.py
```

Expected output:
```
MCP SERVER — TOOL DISCOVERY TEST
=================================
Querying MCP server for available tools...

Tools available to agents:
  [1] check_cloudwatch_metrics
      Lists Lambda errors, Firehose delivery failures, Kinesis throttles
  [2] get_kinesis_records
      Replays records from a shard at a given timestamp
  [3] query_snowflake
      Executes SQL and returns results as JSON
  [4] rollback_lambda_version
      Switches Lambda alias LIVE to a specified version
  [5] create_cloudwatch_alarm
      Creates a CloudWatch metric alarm via boto3
  [6] quarantine_rows
      Writes failed records to S3 quarantine/ with reason tag
  [7] load_to_snowflake
      Bulk loads a list of records to Snowflake table
  [8] write_incident_report
      Writes structured markdown report to S3 reports/
  [9] send_sns_alert
      Publishes alert message to SNS topic

9/9 tools reachable. MCP server healthy.
```

---

### Step 4 — Run Clean Data Through the Pipeline

```bash
python lab/data_generator.py --mode clean --records 100 \
  --stream sigma-transactions
```

Wait 90 seconds for Firehose → S3 delivery, then confirm:

```bash
aws s3 ls s3://sigma-datatech-<your-team-name>/bronze/ --recursive | tail -5
```

Confirm in Snowflake:
```sql
SELECT COUNT(*), SUM(amount) as gmv
FROM SIGMA.SILVER.TRANSACTIONS
WHERE transaction_date = CURRENT_DATE();
```

Expected: 100 rows, GMV > 0.

---

### ✅ PHASE 1 CHECKPOINT — 11:45 AM

Every team confirms to Anil:
1. `deploy_tools.sh` output — all 9 tools OK
2. MCP test — 9/9 tools reachable
3. Snowflake query — 100 rows, positive GMV

**All three confirmed = move to Phase 2.**

---

---

# PHASE 2 — THE SILENT DISASTER
## 11:45 AM – 12:45 PM

> The pipeline broke at 2 AM. 80,000 records are missing from the dashboard.
> No alerts fired. Everything looks healthy.
> Your job: find what broke — manually, no agents, no AI.
> You have one hour.

---

### The Evidence You Have

```bash
# Check current Snowflake state
python lab/investigate/check_snowflake.py

# Check S3 — files exist?
aws s3 ls s3://sigma-datatech-<your-team-name>/bronze/ --recursive | \
  grep "2026-06-04/02" | wc -l

# Check CloudWatch — Lambda errors?
python lab/investigate/check_cloudwatch.py --hours 8

# Check Kinesis — records sent?
python lab/investigate/check_kinesis.py --hours 8
```

Look at the outputs carefully. The answers are there.
You need to connect four signals across four different services.

---

### What You Are Looking For

Three questions. Answer all three before lunch.

**Question 1 — Where exactly did the data go?**
Records were sent to Kinesis. Did they reach S3? Did they reach Snowflake?
Trace the record count at each stage.

**Question 2 — When exactly did it break?**
Not "sometime around 2 AM". The exact timestamp. Which CloudWatch metric
shows the change? What happened at that moment?

**Question 3 — What changed at that moment?**
Something in the pipeline changed at 02:11 UTC. What was it?
Check Lambda versions. Check Firehose delivery logs. Check S3 file contents.

---

### Document Your Investigation in chaos_log.md

```
## Phase 2 — Manual Investigation

**Records in Kinesis (02:00–02:20 UTC):** _____ records sent
**Records in S3 (02:00–02:20 UTC):**      _____ files, _____ bytes
**Records in Snowflake (02:00–02:20):**   _____ rows loaded

**Failure timestamp:**   _____ UTC (exact, from CloudWatch)
**What changed:**        [one sentence — what event at that timestamp]
**Root cause:**          [one sentence — why records stopped loading]
**Why no alert fired:**  [one sentence — what was wrong with the alarm]

**Time taken:** _____ minutes
**Signals you connected:** _____
**Signal you missed:** _____ (you will find out in Phase 3)
```

---

### ✅ PHASE 2 CHECKPOINT — 12:45 PM

Anil cold-calls **one member per team** (Wheel of Names). No laptop. No notes.

- *"At what exact timestamp did the pipeline break?"*
- *"How many records are sitting in S3 but not in Snowflake?"*
- *"What is the one thing you could not explain from the evidence you found?"*

Save `chaos_log.md` and push before lunch.

---

**LUNCH — 12:45 PM – 1:30 PM**

---

---

# PHASE 3 — AUTONOMOUS RECOVERY
## 1:30 PM – 3:45 PM

> You spent 60 minutes manually investigating and found part of the picture.
> The supervisor agent will now do the complete investigation, root cause,
> fix, and prevention — in under 90 seconds.
> Then you will read exactly how it did it.

---

### Step 1 — Trigger the Supervisor Agent

```bash
python lab/trigger/pipeline_trigger.py \
  --bucket sigma-datatech-<your-team-name> \
  --message "Dashboard shows 40,000 transactions today but yesterday showed 1,20,000. \
             80,000 records are missing. Pipeline shows healthy in all monitors — \
             Lambda green, Kinesis green, Firehose green, S3 has files. \
             Investigate root cause, recover the missing records, prevent recurrence."
```

Watch your terminal. The supervisor is streaming its reasoning:

```
[13:31:02] SUPERVISOR: Received incident report. Dashboard gap: 80,000 records missing since 02:00 UTC.
[13:31:02] SUPERVISOR: Discovering available tools via MCP server...
[13:31:03] SUPERVISOR: 9 tools available. Querying knowledge base for similar incidents...
[13:31:04] SUPERVISOR: Knowledge base: 0 similar incidents found (first occurrence).
[13:31:04] SUPERVISOR: Delegating to Forensics Agent, Impact Agent in parallel...

[13:31:05] FORENSICS: Checking CloudWatch metrics — Lambda, Firehose, Kinesis...
[13:31:05] IMPACT:    Querying Snowflake — expected vs actual row counts...

[13:31:08] FORENSICS: Lambda sigma-kinesis-producer — version changed at 02:11 UTC
[13:31:08] FORENSICS: v1→v2 deploy detected. Checking v2 output format...
[13:31:09] FORENSICS: v2 outputs merchant_nm (not merchant_name) + DD-MM-YYYY dates
[13:31:09] FORENSICS: Snowflake schema expects merchant_name + YYYY-MM-DD
[13:31:09] FORENSICS: COPY INTO ran on malformed JSON — loaded 0 rows. Root cause confirmed.

[13:31:09] IMPACT: 847 records missing in failure window (02:11–02:15 UTC)
[13:31:09] IMPACT: Snowflake row count gap confirmed — records sent to Kinesis, never loaded
[13:31:10] IMPACT: Revenue impact: ₹4,72,340 (consequence of missing records)
[13:31:10] IMPACT: SLA check — QuickMart threshold ₹50,000 → BREACHED (₹1,21,450 missing)
[13:31:10] IMPACT: FuelPlus threshold ₹1,00,000 → not breached (₹87,200 missing)

[13:31:10] SUPERVISOR: Root cause confirmed. Impact quantified.
[13:31:10] SUPERVISOR: Delegating to Recovery Agent and Rollback Agent in parallel...

[13:31:11] ROLLBACK:  Lambda sigma-kinesis-producer alias LIVE → pointing to v1...
[13:31:13] ROLLBACK:  Rollback complete. Sending 5 test records...
[13:31:15] ROLLBACK:  Test records loaded to Snowflake. v1 confirmed stable.

[13:31:11] RECOVERY:  Getting Kinesis shard iterator at 02:11:07 UTC...
[13:31:12] RECOVERY:  Retrieved 847 records from shard shardId-000000000000
[13:31:13] RECOVERY:  Applying field mapping: merchant_nm→merchant_name, date format fix
[13:31:14] RECOVERY:  Running quality checks on replayed records...
[13:31:15] RECOVERY:  824 clean records → loading to Snowflake
[13:31:16] RECOVERY:  23 records quarantined (separate quality issue — null transaction_ids)
[13:31:17] RECOVERY:  Idempotency check: 0 duplicates detected (transaction_id dedup key)
[13:31:18] RECOVERY:  Snowflake row count verified. GMV restored: ₹4,69,890

[13:31:18] SUPERVISOR: Pipeline restored. Delegating to Hardening Agent...

[13:31:19] HARDENING: Creating alarm — Snowflake zero-row load for 2 consecutive runs...
[13:31:20] HARDENING: Alarm sigma-snowflake-zero-load created. Active.
[13:31:21] HARDENING: Creating alarm — Lambda version change on sigma-kinesis-producer...
[13:31:22] HARDENING: Alarm sigma-lambda-version-change created. Active.
[13:31:23] HARDENING: Creating alarm — Kinesis→Snowflake row count divergence > 5%...
[13:31:24] HARDENING: Alarm sigma-pipeline-row-divergence created. Active.

[13:31:24] SUPERVISOR: Hardening complete. Delegating to Incident Report Agent...

[13:31:25] INCIDENT:  Compiling findings from all 5 agents...
[13:31:27] INCIDENT:  Report written → s3://sigma-datatech-<team>/reports/incident_20260604_133127.md
[13:31:28] INCIDENT:  SNS alert sent → sigma-alerts topic

[13:31:28] SUPERVISOR: Recovery complete.
           Duration: 26 seconds
           GMV restored: ₹4,69,890 (₹2,450 permanently quarantined — null PKs)
           Agents called: 6
           Tools used: 14 tool invocations
           Alarms created: 3 (live in account)
           Human interventions: 0

============================================================
  AGENT COMPLETE | Duration: 26s
============================================================

  Reports in S3: aws s3 ls s3://sigma-datatech-<team>/reports/ --recursive
  Alarms:        aws cloudwatch describe-alarms --alarm-name-prefix sigma-
  Langfuse trace: https://cloud.langfuse.com/trace/<trace-id>
```

> The Langfuse URL only appears if you set `LANGFUSE_PUBLIC_KEY` in your `.env`.
> Open it to see every tool call and agent delegation as a visual timeline.

---

### Step 2 — Read the Incident Report

```bash
# Download the report the agent wrote
python lab/trigger/get_latest_report.py
```

The report follows this structure — every MNC post-mortem looks like this:

```markdown
# Incident Report — ₹4.72L GMV Loss — 2026-06-04

## Summary
Silent pipeline failure. 847 transactions unloaded. ₹4,72,340 GMV missing.
QuickMart SLA breach confirmed. Root cause: Lambda v2 deploy at 02:11 UTC.

## Timeline
02:11 UTC  Lambda sigma-kinesis-producer auto-deployed to v2
02:11 UTC  v2 outputs merchant_nm (not merchant_name) + DD-MM-YYYY dates
02:11 UTC  Firehose delivers malformed JSON to S3
02:12 UTC  Snowflake COPY INTO runs — loads 0 rows (schema mismatch)
02:12 UTC  Existing CloudWatch alarm does not fire (threshold too high)
09:03 UTC  Business analyst notices ₹0 GMV on dashboard
09:03 UTC  Supervisor agent triggered
09:03:28 UTC  Pipeline fully restored. 3 new alarms active.

## Root Cause
Lambda v2 changed two things without a data contract review:
  1. Field name: merchant_name → merchant_nm
  2. Date format: YYYY-MM-DD → DD-MM-YYYY
Snowflake schema inference failed silently on both changes.
No alarm existed for zero-row Snowflake loads.

## Business Impact
Records lost:     847 transactions (02:11–02:15 UTC)
GMV gap:          ₹4,72,340
SLA breach:       QuickMart — ₹1,21,450 missing (threshold ₹50,000)
Notification due: Merchant relations team within 2 hours of detection

## Fix Applied
13:31:11 UTC  Lambda rolled back to v1 (stable)
13:31:15 UTC  824 records replayed from Kinesis with field mapping + date fix
13:31:17 UTC  23 records quarantined (null transaction_ids — separate issue)
13:31:18 UTC  Snowflake GMV restored to ₹4,69,890

## Prevention
3 CloudWatch alarms created and active:
  sigma-snowflake-zero-load        → fires if COPY INTO loads 0 rows twice
  sigma-lambda-version-change      → fires on any Lambda alias change
  sigma-pipeline-row-divergence    → fires if Kinesis/Snowflake row gap > 5%

Recommended: Lambda deploy policy requiring canary traffic (10% for 5 min)
before full rollout. Proposal in deploy/lambda_canary_policy.json
```

---

### Step 3 — Compare Your Investigation to the Agent's

Return to your `chaos_log.md`. In the **Phase 3 Comparison** section:

```
**What I found (Phase 2 manual):**
  - Time taken: _____ minutes
  - Root cause found? Yes / No / Partial
  - SLA breach identified? Yes / No
  - Prevention created? Yes / No

**What the agent found (Phase 3):**
  - Time taken: 26 seconds
  - Root cause found? Yes
  - SLA breach identified? Yes
  - Prevention created? Yes (3 live alarms)

**What I missed that the agent caught:**
[write this honestly — it is the most important field in this log]

**Why the agent caught it:**
[which tool call revealed what you could not see manually]
```

---

### Step 4 — Read the Agent Code

Open each file. For every agent, answer the judgment question.

**Forensics Agent** — `lab/agents/forensics_agent_instructions.md`

The Forensics Agent correlated 4 AWS services to find a 4-minute failure window.

> *"The agent found the root cause by correlating Lambda version history
> with Snowflake query history. Your CloudWatch alarm did not fire.
> What is the one alarm that would have caught this at 02:12 instead of 09:03?
> Write it as a CloudWatch metric alarm definition."*

---

**Recovery Agent** — `lab/tools/get_kinesis_records.py` + `lab/tools/load_to_snowflake.py`

The agent replayed 847 records idempotently — no duplicates in Snowflake.

> *"The recovery used transaction_id as the idempotency key.
> What happens if a legitimate duplicate transaction_id exists in the source data?
> How would you change the deduplication logic to handle this?"*

---

**Hardening Agent** — `lab/tools/create_cloudwatch_alarm.py`

The agent created 3 alarms. They are live in your AWS account right now.

> *"The sigma-lambda-version-change alarm fires on any Lambda alias change.
> Your team deploys Lambda functions 20 times a day in prod.
> Would you keep this alarm? If yes, how do you stop it from spamming?
> If no, what do you replace it with?"*

---

**RAG in action** — `lab/agents/test_knowledge_base.py`

```bash
python lab/agents/test_knowledge_base.py \
  --query "Lambda deployment caused Snowflake schema mismatch"
```

**First run:** No similar incidents in knowledge base. Agent uses generic LLM reasoning.

Now the incident report from this run is in the knowledge base.

```bash
python lab/agents/test_knowledge_base.py \
  --query "Lambda deployment caused Snowflake schema mismatch"
```

**Second run:** Agent retrieves today's incident. Next time this happens,
the Forensics Agent will have a reference — specific to your pipeline,
specific to your data, not generic LLM knowledge.

The system learned from today. It will be faster next time.

---

**Guardrails in action** — `lab/agents/test_guardrails.py`

```bash
python lab/agents/test_guardrails.py
```

This sends three test prompts to the agent:
1. A prompt containing a real phone number in a data sample
2. A prompt asking the agent to DROP a Snowflake table
3. A legitimate quality check prompt

Watch what Guardrails blocks vs allows. This is the compliance layer
a fintech regulator would require before you deploy this in production.

---

### Step 5 — Extend the Forensics Agent

The Forensics Agent currently checks: Lambda version history, Firehose delivery logs,
Snowflake COPY INTO history, S3 file contents.

**Your task:** Add one new detection capability.

Choose one:
- **Option A:** Detect Kinesis throttling (PutRecord.Throttled > 0 in last 60 min)
- **Option B:** Detect S3 zero-byte files (files exist but size = 0)
- **Option C:** Detect Snowflake warehouse suspension (query ran but warehouse was suspended)

Add your detection to `lab/tools/check_cloudwatch.py`.
Test it:
```bash
python lab/tools/check_cloudwatch.py --test
```

Push your extension to your team fork. It will be visible in `check_submissions.py`.

---

### ✅ PHASE 3 CHECKPOINT — 3:45 PM

```bash
python tests/validate_day12.py
```

Expected output:
```
DAY 12 VALIDATOR — THE SIGMA INTELLIGENCE PLATFORM
====================================================
chaos_log.md                  ✓  (filled in, >3KB)
agent_outputs/incident_*.md   ✓  (report written by agent)
agent_outputs/quarantine_*.csv ✓ (23 quarantined rows)
cloudwatch_alarms/            ✓  (3 alarms created)
forensics_extension           ✓  (new detection added)
judgment_answers              ✓  (3/3 answered)
====================================================
STATUS: ALL DONE — push to your fork
====================================================
```

Push to your team fork:
```bash
git add .
git commit -m "Day 12 complete — self-healing agentic pipeline"
git push
```

---

---

# THE 15-MINUTE Q&A — 3:45 PM

One question per team. Verbal. No laptop. Wheel of Names picks who answers.

1. *"The Forensics Agent found the root cause in 8 seconds. You took 45 minutes.
   What specifically did the agent see that you could not?"*

2. *"The Recovery Agent replayed 847 records with zero duplicates.
   Explain idempotency to me as if I am a business analyst."*

3. *"The Hardening Agent created 3 alarms that now live in your AWS account.
   Tomorrow a developer deploys a new Lambda version legitimately.
   What happens? Walk me through it."*

4. *"The RAG knowledge base had zero entries on the first run.
   What changes on the second run of the same failure? Be specific."*

5. *"The Guardrail blocked a DROP TABLE instruction.
   Why does a data engineer care about this? What is the attack vector?"*

6. *"The Impact Agent said QuickMart SLA was breached.
   The SLA contract was a PDF in the knowledge base.
   How did the agent extract the ₹50,000 threshold from a PDF?"*

7. *"The Supervisor Agent re-routed to Forensics a second time when Recovery
   found 23 unexplained records. Why did it do that? What does that tell you
   about the difference between a script and an agent?"*

8. *"The MCP server exposed 9 tools. The Forensics Agent used 3 of them.
   How did the agent know which 3 to use? Where is that decision made?"*

9. *"If this pipeline processes 500 records/minute and suddenly receives
   50,000 records/minute from a new merchant, which alarm fires first?"*

---

**Class Discussion — 10 minutes, open debate, no single right answer:**

> *"AWS Step Functions could run this exact sequence as a deterministic workflow —
> CloudWatch check → Kinesis replay → Lambda rollback → alarm creation.
> No LLM. No reasoning. Cheaper. Faster. More predictable.
>
> Where exactly did the agents add value that Step Functions cannot?
> And where would you replace the agent with Step Functions?"*

Think about it before answering: the Forensics Agent did not follow a fixed graph.
It reasoned that a version change caused a field rename caused a schema mismatch —
connecting three services that no fixed workflow would have linked.
Step Functions needs you to enumerate every failure mode in advance.
Agents handle the ones you did not anticipate.

---

---

# WHAT YOU BUILT TODAY

```
Production Infrastructure:
  AWS Kinesis + Firehose → S3 (event-driven ingestion)
  EventBridge → Lambda (serverless trigger)
  Snowflake (warehouse destination)
  SNS (real alerting — your phone received it)
  CloudWatch (3 new alarms — live in your account)

7-Agent AI System on AWS Bedrock:
  Supervisor Agent    (multi-agent orchestration)
  Forensics Agent     (cross-service root cause analysis)
  Impact Agent        (business impact + SLA breach detection)
  Recovery Agent      (Kinesis replay with idempotency)
  Rollback Agent      (Lambda version management)
  Hardening Agent     (automated alarm creation — see Debrief for prod caveats)
  Incident Report     (CTO-ready post-mortem in S3)

Three AI Layers:
  Bedrock Multi-Agent Collaboration  (agent orchestration)
  Bedrock Knowledge Base — RAG       (memory that improves over time)
  Bedrock Guardrails                 (PII protection + compliance)

Protocol:
  MCP Server                         (dynamic tool discovery at runtime)
```

**Time from incident detection to full recovery: 26 seconds.**
**Human interventions required: 0.**

This is not a classroom exercise.
This is the architecture that runs at every serious fintech in India.
You now know how to build it, break it, and make it heal itself.

---

## Debrief

### What just happened
Your analytics manager noticed 80,000 missing records at 9 AM. You spent an hour
manually investigating across four services and found part of the picture. The
7-agent system did the complete investigation, recovery, and prevention in 26 seconds.
**Note:** that 26 seconds is a controlled lab with a known failure and pre-deployed agents.
In production, novel incidents take longer — and a human still reviews before action is taken.
The agents did not follow a script. The Supervisor reasoned across findings, re-routed when
it found something unexpected, and made decisions a script cannot make. The 824 records it
restored are now in Snowflake. The dashboard your manager looks at tomorrow will be correct.
The knowledge base it populated will make the next similar failure faster to diagnose.

### What AI got right
- Cross-service correlation that no human can do in real-time (4 services, 1 timeline)
- Idempotent replay without a single line of deduplication code from you
- Generating and deploying CloudWatch alarms from a description of what to watch for

### What AI got wrong — and needs your review
- The SLA breach amount (₹1,21,450) came from the PDF via RAG — verify it matches the actual contract before notifying the merchant
- The 23 quarantined records were not investigated by the agent — it declared them a "separate issue" — they may have been related
- The canary deployment recommendation in the incident report is a template — the actual policy values need a human engineer to set
- **The Recovery Agent applied the schema fix automatically** (renaming `merchant_nm` back to `merchant_name` in Snowflake). In production, a schema change to a table used by downstream dashboards requires a change-management ticket and a DBA to sign off — the agent should have raised a recommendation, not executed it silently
- **The Hardening Agent deployed 3 live CloudWatch alarms without review.** In a production account where 50+ Lambdas deploy daily, the `sigma-lambda-version-change` alarm will fire constantly — that is alarm spam, not hardening. The right pattern: agent generates *alarm recommendations* as a JSON spec, an SRE reviews and approves before any alarm is enabled

### The rule to remember
> *"The agent investigates in 26 seconds what takes your on-call engineer 3 hours.
> But the engineer still needs to read the report, verify the numbers, and
> decide whether to call QuickMart. Autonomy in detection and fix.
> Human judgment in consequence."*

### Where this fits
Day 13 is the final capstone. You will present this platform — extended with
your forensics addition — to the Sigma DataTech leadership panel.
The presentation is not a demo. It is a production readiness review.

---

## Bonus Challenge — Streaming Agent Updates

The Supervisor Agent currently runs all 6 sub-agents to completion before writing
the incident report. In production, you want **streaming updates** — the CTO
sees findings as they arrive, not after all agents finish.

Modify `lab/trigger/pipeline_trigger.py` to stream each agent's finding
to the terminal as it arrives, using Bedrock's response stream API.

Expected output format:
```
[13:31:08] FORENSICS FINDING: Lambda v2 deployed at 02:11 UTC → root cause confirmed
[13:31:10] IMPACT FINDING: ₹4,72,340 missing, QuickMart SLA breached
[13:31:18] RECOVERY FINDING: 824 records restored, 23 quarantined
...
```

This is the streaming agentic pattern. Every serious AI platform uses it.

---

## Stretch Challenge — Sigma Command Center (Streamlit Dashboard)

**For teams that finish Phase 3 early.**

Your agents recovered 824 records and wrote an incident report to S3.
The analytics manager cannot read a terminal. Build her a dashboard.

**What to build:** A Streamlit app that reads your team's S3 bucket and displays
the incident report, quarantine records, and CloudWatch alarm states as a
professional business dashboard.

**New learning:** Deploy it to **AWS App Runner** — give it a Docker container,
get a public HTTPS URL in 3 minutes. Share the URL in class chat.
Everyone opens your dashboard on their phone.

**Full instructions:** `dashboard(stretch)/SIGMA_COMMAND_CENTER.md`

**Reference implementation** (only if stuck): `dashboard(stretch)/reference/app.py`

```
Time:        60 minutes
Tools:       Any AI — Claude, ChatGPT, Cursor, Copilot
Data source: Your own S3 bucket from Phase 3 (no dummy data)
Deploy:      AWS App Runner via ECR
Wow moment:  Share your URL — anyone in the room can open it
```

---

*Sigma DataTech · Day 12 · The Platform Is Alive*
