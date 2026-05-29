# Snowflake Cortex — Introduction & Feature Demo Guide
*Beginner-friendly | Live demo sequence | Runs entirely in Snowsight Worksheets*

---

## What is Snowflake Cortex?

Cortex is Snowflake's built-in AI layer — LLMs that run **inside your warehouse**, on your data, with no API keys, no data leaving Snowflake, no Python required. Just SQL.

---

## Features at a Glance

| Feature | What It Does | Where You Use It |
|---|---|---|
| `COMPLETE()` | General LLM prompt → text response | SQL worksheet |
| `SUMMARIZE()` | Summarise long text in 1-2 sentences | SQL worksheet |
| `SENTIMENT()` | Returns score -1 (negative) to 1 (positive) | SQL worksheet |
| `TRANSLATE()` | Translate text between languages | SQL worksheet |
| `EXTRACT_ANSWER()` | Extract answer from a passage given a question | SQL worksheet |
| `CLASSIFY_TEXT()` | Classify text into your custom categories | SQL worksheet |
| **Cortex Analyst** | Natural language → SQL via semantic model | Python / REST API |
| **Cortex Search** | Semantic search over unstructured text columns | Python / REST API |

---

## Setup (Run Once Before Demo)

```sql
USE ROLE ACCOUNTADMIN;
USE DATABASE SIGMA_DE;
USE SCHEMA PUBLIC;
USE WAREHOUSE COMPUTE_WH;
```

---

## Demo 1 — COMPLETE() — Ask the LLM Anything

**What to say:** "This is the simplest Cortex feature. One SQL function — you pass a prompt, you get a response. No Python, no API key."

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'mistral-7b',
    'What are the top 3 causes of data pipeline failures in production? Answer in bullet points.'
) AS answer;
```

**Show next — prompt with table data:**
```sql
SELECT
    merchant_name,
    SNOWFLAKE.CORTEX.COMPLETE(
        'mistral-7b',
        'Write a 1-sentence business description for a company called: ' || merchant_name
    ) AS ai_description
FROM DIM_MERCHANT
LIMIT 5;
```

**Teaching point:** "You just ran an LLM on every row in a table with one SQL query. At scale — 1 million rows, same query."

---

## Demo 2 — SENTIMENT() — Instant Sentiment Scoring

**What to say:** "No training, no model setup. Pass any text — get a score between -1 and 1."

```sql
SELECT
    SNOWFLAKE.CORTEX.SENTIMENT('The pipeline ran perfectly, no errors at all!') AS positive_example,
    SNOWFLAKE.CORTEX.SENTIMENT('Data quality is terrible, half the records are missing.') AS negative_example,
    SNOWFLAKE.CORTEX.SENTIMENT('The job completed.') AS neutral_example;
```

**Show on table data:**
```sql
-- Simulate customer feedback on transactions
SELECT
    transaction_id,
    status,
    CASE status
        WHEN 'COMPLETED' THEN 'Transaction processed smoothly, very happy!'
        WHEN 'FAILED' THEN 'Payment failed again, very frustrating experience'
        ELSE 'Transaction is still pending, waiting for update'
    END AS feedback,
    SNOWFLAKE.CORTEX.SENTIMENT(
        CASE status
            WHEN 'COMPLETED' THEN 'Transaction processed smoothly, very happy!'
            WHEN 'FAILED' THEN 'Payment failed again, very frustrating experience'
            ELSE 'Transaction is still pending, waiting for update'
        END
    ) AS sentiment_score
FROM FACT_TRANSACTIONS
LIMIT 10;
```

**Teaching point:** "In production — run this on support tickets, app store reviews, customer emails. No external API, data never leaves Snowflake."

---

## Demo 3 — SUMMARIZE() — Collapse Long Text

**What to say:** "Any long text → 1-2 sentence summary. Useful for logs, reports, incident descriptions."

```sql
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(
    'On January 15th 2024, the Sigma DataTech transaction pipeline experienced a critical failure
     at 02:34 UTC. The root cause was identified as a schema drift in the merchants dimension table
     where a new column payment_gateway was added without updating the Silver layer transformation.
     This caused 3,847 records to fail the quality check and be quarantined. The pipeline was
     halted automatically by the data quality gate. The on-call engineer was paged at 02:41 UTC.
     Fix was deployed at 03:15 UTC. Total downtime: 41 minutes. Revenue impact: $12,400 in
     delayed settlement. Post-incident review scheduled for January 17th.'
) AS incident_summary;
```

**Teaching point:** "Imagine 500 incident reports. One query — all summarised. Feed into a RAG chatbot (Day 9)."

---

## Demo 4 — TRANSLATE() — Instant Translation

**What to say:** "One function, 100+ languages. Useful when your data has multi-language content."

```sql
SELECT
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'hi') AS hindi,
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'de') AS german,
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'fr') AS french;
```

---

## Demo 5 — EXTRACT_ANSWER() — Q&A on Your Text

**What to say:** "Give it a passage and a question — it finds the answer within the text. Useful for policy docs, runbooks, contracts."

```sql
SELECT SNOWFLAKE.CORTEX.EXTRACT_ANSWER(
    'The Sigma DataTech SLA requires all Gold layer tables to be ready by 04:00 UTC daily.
     If the pipeline fails, the on-call engineer must be paged within 5 minutes.
     The maximum acceptable data latency is 2 hours. Revenue tables have priority class P1.
     Customer tables have priority class P2. All incidents must be logged in the runbook
     within 24 hours of resolution.',
    'What is the maximum acceptable data latency?'
) AS extracted_answer;
```

**Try another question on same passage:**
```sql
SELECT SNOWFLAKE.CORTEX.EXTRACT_ANSWER(
    'The Sigma DataTech SLA requires all Gold layer tables to be ready by 04:00 UTC daily.
     If the pipeline fails, the on-call engineer must be paged within 5 minutes.
     The maximum acceptable data latency is 2 hours. Revenue tables have priority class P1.
     Customer tables have priority class P2. All incidents must be logged in the runbook
     within 24 hours of resolution.',
    'What priority class are revenue tables?'
) AS extracted_answer;
```

**Teaching point:** "Day 9 — you build a RAG chatbot over pipeline logs using this exact pattern."

---

## Demo 6 — CLASSIFY_TEXT() — Custom Categories

**What to say:** "You define the categories. Cortex classifies. No training data needed."

```sql
SELECT
    merchant_name,
    category,
    SNOWFLAKE.CORTEX.CLASSIFY_TEXT(
        category,
        ['Essential Services', 'Entertainment & Leisure', 'Travel & Transport', 'Retail Shopping']
    ):"label"::STRING AS ai_classification
FROM DIM_MERCHANT;
```

**Teaching point:** "In production — classify support tickets, categorise transactions, tag pipeline errors by type."

---

## Demo 7 — Cortex Analyst — Natural Language → SQL

**What to say:** "This is the big one. You write a semantic model YAML that describes your tables and business rules. Then anyone — analyst, PM, exec — types a question in English and gets an answer. No SQL knowledge needed."

**Prerequisite:** `sigma_semantic_model.yaml` uploaded to `@SEMANTIC_MODELS` stage (already done).

```python
# Run verify_cortex.py from repo/day6/bonus/
python verify_cortex.py
```

**Then ask these questions live:**
1. `"What is the total revenue by merchant?"`
2. `"Which payment method has the highest failure rate?"`
3. `"Show me the top 5 customers by transaction count"`

**Show the response structure** — Cortex returns:
- The SQL it generated
- The actual results
- A plain-English interpretation

**Teaching point:** "The semantic model is doing what our SCHEMA_RICH prompt did in Module 2 — but it's a permanent, reusable contract. One model file serves every question, forever."

---

## Comparison: Cortex Analyst vs Our NL2SQL (Module 2)

| | Our NL2SQL (boto3) | Cortex Analyst |
|---|---|---|
| Setup | Python + prompt engineering | YAML semantic model |
| Runs on | Bedrock (external) | Snowflake (internal) |
| Latency | ~20s (no execution) | ~60-100s (executes SQL) |
| Returns | SQL only | SQL + results + explanation |
| Control | Full | Bounded by semantic model |
| Cost | Bedrock tokens | Snowflake credits |
| Best for | Custom pipelines, agents | Self-serve analytics |

---

## Available Models in Cortex COMPLETE()

```sql
-- These models are available (no activation needed):
-- 'mistral-7b'          → fast, good for simple tasks
-- 'mistral-large'       → stronger reasoning
-- 'llama3-8b'           → Meta's open model
-- 'llama3-70b'          → Meta's large model (slower, more capable)
-- 'snowflake-arctic'    → Snowflake's own model

-- Try the same prompt on different models:
SELECT
    'mistral-7b' AS model,
    SNOWFLAKE.CORTEX.COMPLETE('mistral-7b', 'Explain data lakehouse in one sentence.') AS response
UNION ALL
SELECT
    'llama3-8b',
    SNOWFLAKE.CORTEX.COMPLETE('llama3-8b', 'Explain data lakehouse in one sentence.');
```

---

## Key Talking Points

1. **No data leaves Snowflake** — security/compliance teams love this
2. **No API keys, no infra** — just SQL, runs in your warehouse
3. **Scales with Snowflake** — run on millions of rows, same syntax
4. **Not a replacement for Bedrock/OpenAI** — no fine-tuning (yet), model choice is limited
5. **Best use case:** enriching data IN the warehouse — sentiment on reviews, summaries of logs, classification of records

---

## Demo Run Order (45 min session)

| Time | Demo | Why This Order |
|---|---|---|
| 5 min | Setup + COMPLETE() basics | Simplest entry point |
| 5 min | COMPLETE() on table rows | Shows scale |
| 5 min | SENTIMENT() | Instantly relatable |
| 5 min | SUMMARIZE() | Practical use case |
| 5 min | EXTRACT_ANSWER() | Connects to RAG (Day 9) |
| 5 min | CLASSIFY_TEXT() | Shows customisation |
| 15 min | Cortex Analyst end-to-end | The wow moment |
