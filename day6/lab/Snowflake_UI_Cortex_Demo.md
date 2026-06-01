# Snowflake Cortex — Live Demo Guide (Snowsight UI Only)
*Everything runs in the browser — no Python, no CLI, no API keys*

---

## What is Snowflake Cortex?

Built-in AI inside Snowflake. LLMs that run **on your data, inside your warehouse**.  
No setup. No external API. Just SQL functions + a dedicated UI for Cortex Analyst.

---

## One-Time Setup (Paste into a new worksheet, run once)

```sql
USE ROLE ACCOUNTADMIN;
USE DATABASE SIGMA_DE;
USE SCHEMA PUBLIC;
USE WAREHOUSE COMPUTE_WH;
```

---

## PART 1 — SQL Functions (All in Snowsight Worksheet)

### How to open a worksheet
Snowsight left sidebar → **Projects** → **Worksheets** → **+ (top right)** → **SQL Worksheet**

---

### Demo 1 — COMPLETE() — Ask the LLM anything

**Note:** *"One SQL function. You pass a prompt. You get a response. No Python, no API key."*

```sql
SELECT SNOWFLAKE.CORTEX.COMPLETE(
    'mistral-7b',
    'What are the top 3 causes of data pipeline failures in production? Answer in bullet points.'
) AS answer;
```

**Now show it running on actual table rows:**
```sql
SELECT
    merchant_name,
    category,
    SNOWFLAKE.CORTEX.COMPLETE(
        'mistral-7b',
        'Write a 1-sentence business description for a company called: ' || merchant_name
    ) AS ai_generated_description
FROM DIM_MERCHANT
LIMIT 5;
```

**Note:** *"You just ran an LLM on every row in your table. At 1 million rows — same query, same syntax."*

> **DEBRIEF — Why this is remarkable:**
> Every other AI tool requires you to export your data, call an external API, handle authentication, manage rate limits, and bring results back. Here you wrote 6 lines of SQL. The LLM came to your data — your data didn't go to the LLM. That is a fundamental shift in how AI gets applied to enterprise data. No security review needed. No data governance headache. No extra infrastructure bill.

---

### Demo 2 — SENTIMENT() — Score any text -1 to +1

**Note:** *"No training, no setup. Pass text, get a sentiment score. Negative = -1, Positive = +1."*

```sql
SELECT
    SNOWFLAKE.CORTEX.SENTIMENT('Transaction processed smoothly, very happy!')    AS positive,
    SNOWFLAKE.CORTEX.SENTIMENT('Payment failed again, very frustrating!')         AS negative,
    SNOWFLAKE.CORTEX.SENTIMENT('Transaction is pending.')                          AS neutral;
```

**Now show it on real data:**
```sql
SELECT
    transaction_id,
    status,
    SNOWFLAKE.CORTEX.SENTIMENT(
        CASE status
            WHEN 'COMPLETED' THEN 'Great experience, payment went through instantly!'
            WHEN 'FAILED'    THEN 'Payment failed again, extremely frustrated'
            ELSE                  'Still waiting for transaction to complete'
        END
    ) AS sentiment_score
FROM FACT_TRANSACTIONS
LIMIT 10;
```

**Note:** *"In production — run this on support tickets, app reviews, customer emails. Data never leaves Snowflake."*

> **DEBRIEF — Why this matters:**
> Traditional sentiment analysis requires a trained ML model, labelled training data, a feature pipeline, a model serving endpoint, and ongoing retraining as language evolves. That is a 3-month project. What you just did took 30 seconds. Cortex has a pre-trained model baked in — you call it like a SQL function. The business value: imagine running this on 2 million customer support tickets overnight and waking up to a dashboard showing sentiment trends by product, city, and payment method. Zero ML team required.

---

### Demo 3 — SUMMARIZE() — Collapse long text to 1-2 sentences

**Note:** *"Paste any long text — incident report, document, log — get a crisp summary."*

```sql
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(
    'On January 15th 2024, the Sigma DataTech transaction pipeline experienced a critical failure
     at 02:34 UTC. The root cause was a schema drift in the merchants dimension table where a
     new column payment_gateway was added without updating the Silver layer transformation.
     This caused 3,847 records to fail the quality check and be quarantined. The pipeline was
     halted automatically by the data quality gate. The on-call engineer was paged at 02:41 UTC.
     Fix was deployed at 03:15 UTC. Total downtime: 41 minutes. Revenue impact: $12,400 in
     delayed settlement. Post-incident review scheduled for January 17th.'
) AS summary;
```

**Note:** *"500 incident reports, one query, all summarised. This feeds directly into the RAG chatbot on Day 9."*

> **DEBRIEF — Why this is production-useful:**
> Data teams accumulate thousands of incident reports, pipeline logs, and runbook entries over time. Nobody reads them. They become dead archives. SUMMARIZE() turns that archive into a queryable, digestible asset. Run it on every incident report in your table — now you have a one-sentence summary column. Feed those summaries into a RAG chatbot (Day 9) and your on-call engineer can ask "what failed last month and why?" and get an instant answer. The data was always there — Cortex makes it accessible.

---

### Demo 4 — TRANSLATE() — Instant translation, 100+ languages

```sql
SELECT
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'hi') AS hindi,
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'de') AS german,
    SNOWFLAKE.CORTEX.TRANSLATE('Pipeline failed due to schema mismatch', 'en', 'fr') AS french;
```

> **DEBRIEF — The real use case:**
> Global companies store customer feedback, support tickets, and product reviews in 20+ languages. Previously you needed a separate translation service, per-language model management, and manual data pipelines to normalize everything to English before analysis. Now it is one SQL column in your existing pipeline. Add TRANSLATE() before SENTIMENT() — suddenly your multilingual feedback table has a uniform sentiment score. That is two Cortex functions, chained, no code outside SQL.

---

### Demo 5 — EXTRACT_ANSWER() — Q&A on any passage

**Note:** *"Give it a document and a question — it finds the answer within the text. Think: policy docs, runbooks, contracts."*

```sql
SELECT SNOWFLAKE.CORTEX.EXTRACT_ANSWER(
    'The Sigma DataTech SLA requires all Gold layer tables to be ready by 04:00 UTC daily.
     If the pipeline fails, the on-call engineer must be paged within 5 minutes.
     The maximum acceptable data latency is 2 hours. Revenue tables have priority class P1.
     Customer tables have priority class P2. All incidents must be logged within 24 hours.',
    'What is the maximum acceptable data latency?'
) AS answer;
```

**Run again with a different question on the same passage:**
```sql
SELECT SNOWFLAKE.CORTEX.EXTRACT_ANSWER(
    'The Sigma DataTech SLA requires all Gold layer tables to be ready by 04:00 UTC daily.
     If the pipeline fails, the on-call engineer must be paged within 5 minutes.
     The maximum acceptable data latency is 2 hours. Revenue tables have priority class P1.
     Customer tables have priority class P2. All incidents must be logged within 24 hours.',
    'What priority class are revenue tables?'
) AS answer;
```

**Note:** *"Same function, different question, same document. This is the building block of RAG."*

> **DEBRIEF — This is RAG in its simplest form:**
> What you just saw is Retrieval-Augmented Generation stripped to its essence — give the model a context passage, ask a question, get the answer extracted from that passage. In Day 9 you will scale this: instead of one hardcoded passage, you will retrieve the most relevant log entries from a vector database and feed them to the model dynamically. But the core mechanic is identical to what you just ran. EXTRACT_ANSWER() is the conceptual foundation of every enterprise RAG system.

---

### Demo 6 — CLASSIFY_TEXT() — Your categories, AI does the classification

**Note:** *"You define the categories. Cortex classifies. No training data, no model fine-tuning."*

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

**Note:** *"In production — classify support tickets, tag pipeline errors by type, categorise transactions automatically."*

> **DEBRIEF — Zero-shot classification is the superpower here:**
> Traditional text classification requires labelled training data (hundreds or thousands of examples per category), model training, validation, deployment, and retraining whenever categories change. CLASSIFY_TEXT() needs none of that. You define new categories in the SQL query itself — no retraining, no redeployment, just change the array. This is called zero-shot classification — the model has never seen your categories before but classifies correctly because it understands language semantics. For a data engineer, this means any new tagging or categorization requirement is a one-line SQL change, not a 2-month ML project.

---

### Demo 7 — Try Different Models with COMPLETE()

**Note:** *"Cortex gives you multiple models. Same prompt, different models — compare quality vs speed."*

```sql
SELECT 'mistral-7b' AS model,
    SNOWFLAKE.CORTEX.COMPLETE('mistral-7b',
        'Explain the medallion architecture in one sentence for a business audience.') AS response
UNION ALL
SELECT 'llama3-8b',
    SNOWFLAKE.CORTEX.COMPLETE('llama3-8b',
        'Explain the medallion architecture in one sentence for a business audience.')
UNION ALL
SELECT 'snowflake-arctic',
    SNOWFLAKE.CORTEX.COMPLETE('snowflake-arctic',
        'Explain the medallion architecture in one sentence for a business audience.');
```

**Available models:** `mistral-7b`, `mistral-large`, `llama3-8b`, `llama3-70b`, `snowflake-arctic`

> **DEBRIEF — Model selection is an engineering decision, not a preference:**
> Smaller models (mistral-7b, llama3-8b) are faster and cheaper — use them for high-volume, simple tasks like sentiment scoring or classification at row level. Larger models (mistral-large, llama3-70b) reason better — use them for complex summarisation, code generation, or multi-step reasoning. snowflake-arctic is Snowflake's own model optimised for enterprise SQL and analytics tasks. The right pattern: use the smallest model that gives acceptable quality for your use case. Never reach for the biggest model by default — you pay per token and latency goes up.

---

## PART 2 — Cortex Analyst (Dedicated UI in Snowsight)

**Note:** *"Now the big feature. No SQL needed at all — just type a question in English."*

### How to open Cortex Analyst in Snowsight

1. Left sidebar → look for **AI & ML** section (below Monitoring)
2. Click **Cortex Analyst**
3. Click **+ New conversation**
4. Under **Semantic model** → click **Select** → browse to stage `@SIGMA_DE.PUBLIC.SEMANTIC_MODELS` → select `sigma_semantic_model.yaml`
5. Click **Start conversation**

### Questions to ask live (type these one by one):

1. `What is the total revenue by merchant?`
2. `Which payment method has the highest failure rate?`
3. `Show me the top 5 merchants by transaction count`
4. `What was the revenue trend over the last 2 weeks?`
5. `Which customers spent more than $500?`

### What to point out on screen after each answer:
- **The SQL tab** — "Cortex wrote this SQL. You can inspect and audit it."
- **The Results tab** — "Actual data from your warehouse, not a hallucination."
- **The Explanation** — "It tells you in plain English what it found."

**Note:** *"A PM, analyst, or exec can now query your warehouse without knowing SQL. And every query is auditable — you see exactly what SQL ran."*

> **DEBRIEF — Why Cortex Analyst is different from ChatGPT with a database:**
> When someone asks ChatGPT a data question, it guesses — it has no access to your actual data. Cortex Analyst is grounded in your semantic model, which defines your exact tables, columns, business rules, and metric definitions. It cannot hallucinate a table that doesn't exist. It cannot get revenue wrong because the business rule is in the YAML. And critically — every single answer is backed by auditable SQL. You can show a CFO the exact query that produced the revenue number. That auditability is what makes this enterprise-grade, not just a cool demo.

---

## PART 3 — Side-by-Side Comparison (Show on Screen)

| | SQL Functions (Part 1) | Cortex Analyst (Part 2) |
|---|---|---|
| Who uses it | Data Engineers, SQL writers | Business users, analysts, PMs |
| Interface | SQL worksheet | Chat UI |
| Input | SQL with LLM function calls | Plain English questions |
| Output | Transformed/enriched data | SQL + results + explanation |
| Setup needed | None — just call the function | Semantic model YAML |
| Our equivalent | `boto3` + Bedrock (Module 2) | Same concept, built into Snowflake |

---

## Overall Debrief — What Makes Cortex Different

> **The one thing to remember from this demo:**
> Every AI capability you just saw — summarisation, sentiment, classification, translation, Q&A, natural language to SQL — these are not new ideas. They exist in OpenAI, Bedrock, HuggingFace. What Cortex does differently is bring the AI to where your data already lives. No ETL to move data out. No API integration to bring results back. No security exceptions to approve. No separate infrastructure to manage. For a data engineer working inside Snowflake, that means AI becomes a native part of your data pipeline — one more function in a SELECT statement, not a separate system to build and maintain.
>
> **The limitation to be honest about:**
> Cortex gives you a curated set of models — you cannot fine-tune them, you cannot bring your own model (yet), and model availability depends on your Snowflake region. For custom fine-tuning, domain-specific models, or cutting-edge models the moment they release — you still need Bedrock or direct API access. Cortex and Bedrock are not competitors; they solve different layers of the same problem.

---

## Demo Run Order (45 min)

| Time | What | Key Message |
|---|---|---|
| 2 min | Setup worksheet | Role, DB, schema |
| 5 min | COMPLETE() basics + table rows | LLM at warehouse scale |
| 5 min | SENTIMENT() | Instant scoring, no training |
| 5 min | SUMMARIZE() | Collapses logs/reports |
| 3 min | TRANSLATE() | Multi-language in one SQL column |
| 5 min | EXTRACT_ANSWER() | RAG building block |
| 5 min | CLASSIFY_TEXT() | Zero-shot, no training data |
| 3 min | Compare models | Engineering decision: size vs speed |
| 7 min | Cortex Analyst UI | The wow moment — English → SQL → results |
