# BONUS LAB — Snowflake Cortex Analyst
### Day 6 | GenAI for Data Engineering | Sigma DataTech Training

---

## MISSION BRIEFING

> **FROM:** Vikram Nair, CTO — Sigma DataTech  
> **TO:** Data Engineering Intern Batch  
> **SUBJECT:** Evaluate Cortex Analyst for Production Self-Serve Analytics
>
> In Module 2 you built NL2SQL from scratch. It took 200 lines of code,
> a carefully crafted schema prompt, few-shot examples, a validator,
> an executor, and an audit logger. It works — but every new table
> needs schema context manually added, every business rule needs a prompt
> update, and accuracy still depends on how well we write the system prompt.
>
> Snowflake just GA'd Cortex Analyst — their own NL→SQL engine built
> into the warehouse. No external API, no prompt engineering, no code
> to maintain. You describe your data in a YAML file, and Cortex handles
> the rest.
>
> **Your mission:** Set up Cortex Analyst on the same Sigma DataTech data,
> ask the same 5 questions you tested in Module 2, and decide which approach
> you would recommend for production and why.
>
> Time target: 45 minutes.

---

## WHAT YOU WILL BUILD

1. A **Semantic Model YAML** — the "source of truth" file that describes
   your Snowflake tables, columns, joins, and business rules to Cortex
2. A **Cortex Analyst REST API client** in Python
3. A **side-by-side comparison** of Cortex Analyst vs your Module 2 NL2SQL
   on the same 5 business questions

---

## UNDERSTANDING CORTEX ANALYST (Read This Carefully)

In Module 2 your NL2SQL prompt had to contain:
- Full DDL (CREATE TABLE statements)
- Column business descriptions
- JOIN relationships
- Business rules
- Few-shot examples

In Cortex Analyst, all of this moves into a **Semantic Model YAML file**.
This YAML lives in a Snowflake stage (like an S3 object) and Cortex reads it
at query time. You write the YAML once — Cortex does the prompt engineering.

```
LAB 3 ARCHITECTURE:
You → (schema context in prompt) → Nova Pro → SQL → Snowflake
      ↑
      You maintain this manually

CORTEX ANALYST ARCHITECTURE:
You → REST API call → Cortex Analyst → SQL → Snowflake
                           ↑
                  Reads semantic model YAML (you write once)
```

The key advantage: Cortex Analyst is bounded by the semantic model.
It cannot hallucinate table names that are not in the YAML.
It knows your join paths because you declared them in YAML.
It knows your business rules because you wrote them in verified_queries.

---

## PREREQUISITES (2 minutes — shared account, key-pair auth)

### Snowflake Access — Use Trainer's Shared Account

Cortex Analyst requires a paid Snowflake account. The trainer has set up a
shared read-only account with Cortex access enabled for the class.
Authentication is via key-pair (no password, no MFA).

**What you need:**
```
Account:   GEJKIOG-TKC55632
Username:  student_genai
Auth:      Key-pair (student_key.p8 file — shared on Slack)
Role:      STUDENT_CORTEX
Warehouse: COMPUTE_WH
Database:  SIGMA_DE
```

### Step 1 — Get the private key file

Download `student_key.p8` from Slack/WhatsApp (trainer will share).
Place it in your `day6/bonus/` folder.

### Step 2 — Install packages
```bash
pip install snowflake-connector-python cryptography requests
```

### Step 3 — Verify Access
```bash
cd day6/bonus
python verify_cortex.py
```

**Expected output:**
```
Connecting to Snowflake...
Testing Cortex AI...
  Cortex response: OK
Testing data access...
  Row count: 50

All good! Cortex + data access verified.
```

If you see this — you're ready. If it says `student_key.p8 not found` — download it from Slack first.

### What you CAN do with this account:
- SELECT from all tables in SIGMA_DE.PUBLIC
- Use all Cortex AI functions (COMPLETE, Analyst)
- Upload files to the SEMANTIC_MODELS stage
- Run queries via Python connector

### What you CANNOT do (read-only safety):
- DROP, DELETE, INSERT, UPDATE on any table
- Create new databases or schemas
- Modify account settings

---

## MILESTONE 1 — Trainer will create the Semantic Model YAML

**What we're doing:** As this is a shared account and you are using trainer's credentials, Trainer will create YAML file that replaces all the schema context we manually wrote in Module 2. This is the single most important file in the Cortex Analyst setup.

**Just read and understand the file.**


The YAML has four main sections:
- `tables` — describe each table and its columns
- `relationships` — declare JOIN paths between tables
- `metrics` — pre-define calculated business measures (like revenue)
- `verified_queries` — your few-shot examples (Cortex calls them verified)

File Name `sigma_semantic_model.yaml`:

```yaml
# ============================================================
# sigma_semantic_model.yaml
# Cortex Analyst Semantic Model for Sigma DataTech
# This file replaces all schema context from Module 2's system prompt
# ============================================================

name: sigma_datatech_analytics
description: >
  Semantic model for Sigma DataTech payment analytics.
  Covers transaction facts and merchant dimension.
  Data covers January 2024 (50 sample transactions, 5 merchants).

# ── TABLES ─────────────────────────────────────────────────
# Describe every table Cortex can query.
# The better your column descriptions, the more accurate Cortex will be.

tables:
  - name: FACT_TRANSACTIONS
    description: >
      One row per payment transaction processed by Sigma DataTech.
      This is the primary fact table. Contains 4M rows per day in production.
      Our lab sample has 50 rows covering Jan 2024.
    base_table:
      database: SIGMA_DE
      schema: PUBLIC
      table: FACT_TRANSACTIONS

    columns:
      - name: TRANSACTION_ID
        description: Unique identifier for each transaction. Format TXN001.
        data_type: VARCHAR

      - name: AMOUNT
        description: >
          Transaction value in US Dollars (USD).
          IMPORTANT: This column records the attempted amount for ALL transactions
          including FAILED and PENDING ones. It is NOT the same as revenue.
          Revenue must filter on STATUS = 'COMPLETED'.
        data_type: NUMBER

      - name: STATUS
        description: >
          Outcome of the transaction attempt.
          COMPLETED = payment successful, money moved.
          FAILED = payment rejected (insufficient funds, card declined, etc).
          PENDING = payment initiated but not yet settled.
        data_type: VARCHAR
        sample_values:
          - COMPLETED
          - FAILED
          - PENDING

      - name: MERCHANT_ID
        description: >
          Identifier of the merchant who received (or attempted to receive) payment.
          This is a foreign key — join to DIM_MERCHANT for merchant name and category.
          Format: MERCH_001, MERCH_002, etc.
        data_type: VARCHAR

      - name: CUSTOMER_ID
        description: >
          Identifier of the customer who initiated the transaction.
          Format: CUST_001, CUST_002, etc.
          Customer details not available in current schema.
        data_type: VARCHAR

      - name: TRANSACTION_DATE
        description: >
          Calendar date the transaction was initiated.
          Data type is DATE (not TIMESTAMP).
          Use format 'YYYY-MM-DD' for filtering.
          Our lab data: 2024-01-15 through 2024-01-31.
        data_type: DATE

      - name: PAYMENT_METHOD
        description: >
          Payment instrument used for the transaction.
          CREDIT_CARD = Visa/Mastercard credit cards.
          DEBIT_CARD = Bank debit cards.
          UPI = Unified Payments Interface (India's real-time payment system).
        data_type: VARCHAR
        sample_values:
          - CREDIT_CARD
          - DEBIT_CARD
          - UPI

  - name: DIM_MERCHANT
    description: >
      Merchant master data. One row per registered merchant partner.
      Join to FACT_TRANSACTIONS using MERCHANT_ID to get merchant names.
      Always use MERCHANT_NAME (not MERCHANT_ID) in end-user results.
    base_table:
      database: SIGMA_DE
      schema: PUBLIC
      table: DIM_MERCHANT

    columns:
      - name: MERCHANT_ID
        description: >
          Primary key for merchants. Format MERCH_001.
          Matches FACT_TRANSACTIONS.MERCHANT_ID.
        data_type: VARCHAR

      - name: MERCHANT_NAME
        description: >
          Human-readable merchant name. Always use this in output instead
          of MERCHANT_ID codes. Examples: Swiggy, Flipkart, Zepto.
        data_type: VARCHAR

      - name: CATEGORY
        description: >
          Business category of the merchant.
          Examples: Food Delivery, E-Commerce, Grocery Delivery,
          Entertainment, Travel.
        data_type: VARCHAR

      - name: CITY
        description: >
          City where the merchant is headquartered.
          Examples: Bengaluru, Mumbai, Gurugram.
        data_type: VARCHAR

# ── RELATIONSHIPS ───────────────────────────────────────────
# Declare all join paths. Cortex uses this to know which tables
# to join and on which columns — no guessing required.

relationships:
  - name: transactions_to_merchant
    description: >
      Links each transaction to its merchant for name and category lookups.
      Always use this join when merchant name or category is needed in output.
    left_table: FACT_TRANSACTIONS
    right_table: DIM_MERCHANT
    join_type: MANY_TO_ONE
    relationship_columns:
      - left_column: MERCHANT_ID
        right_column: MERCHANT_ID

# ── METRICS ─────────────────────────────────────────────────
# Pre-defined business measures. Cortex uses these when users ask
# about metrics like "revenue" or "failure rate".
# This ensures business rules are always applied correctly.

metrics:
  - name: total_revenue
    description: >
      Total revenue from completed transactions only.
      COMPLETED transactions represent money that actually moved.
      FAILED and PENDING are excluded from revenue.
    type: number
    expr: "SUM(CASE WHEN FACT_TRANSACTIONS.STATUS = 'COMPLETED' THEN FACT_TRANSACTIONS.AMOUNT ELSE 0 END)"
    table: FACT_TRANSACTIONS

  - name: failure_rate_pct
    description: >
      Percentage of transactions that failed.
      Calculated as (failed count / total count) * 100.
      Expressed as a percentage between 0 and 100.
    type: number
    expr: "ROUND(100.0 * SUM(CASE WHEN FACT_TRANSACTIONS.STATUS = 'FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2)"
    table: FACT_TRANSACTIONS

  - name: completed_transaction_count
    description: Count of successfully completed transactions.
    type: number
    expr: "SUM(CASE WHEN FACT_TRANSACTIONS.STATUS = 'COMPLETED' THEN 1 ELSE 0 END)"
    table: FACT_TRANSACTIONS

# ── VERIFIED QUERIES ────────────────────────────────────────
# These are manually verified question → SQL pairs.
# Cortex Analyst uses these like few-shot examples —
# if a user's question closely matches a verified query,
# Cortex uses that SQL as a high-confidence template.
# Add your most common business questions here over time.

verified_queries:
  - name: total_transaction_count
    question: How many transactions are in the system?
    sql: "SELECT COUNT(*) AS TOTAL_TRANSACTIONS FROM FACT_TRANSACTIONS"
    verified_by: Sigma DataTech Data Engineering Team
    verified_at: "2024-01-31"

  - name: failed_transaction_count
    question: How many transactions failed?
    sql: "SELECT COUNT(*) AS FAILED_COUNT FROM FACT_TRANSACTIONS WHERE STATUS = 'FAILED'"
    verified_by: Sigma DataTech Data Engineering Team
    verified_at: "2024-01-31"

  - name: revenue_by_merchant
    question: Which merchant had the highest revenue?
    sql: |
      SELECT
          m.MERCHANT_NAME,
          SUM(CASE WHEN t.STATUS = 'COMPLETED' THEN t.AMOUNT ELSE 0 END) AS REVENUE_USD
      FROM FACT_TRANSACTIONS t
      JOIN DIM_MERCHANT m ON t.MERCHANT_ID = m.MERCHANT_ID
      GROUP BY m.MERCHANT_NAME
      ORDER BY REVENUE_USD DESC
      LIMIT 1
    verified_by: Sigma DataTech Data Engineering Team
    verified_at: "2024-01-31"

  - name: failure_rate_by_payment_method
    question: What is the failure rate for each payment method?
    sql: |
      SELECT
          PAYMENT_METHOD,
          COUNT(*) AS TOTAL,
          SUM(CASE WHEN STATUS = 'FAILED' THEN 1 ELSE 0 END) AS FAILED,
          ROUND(100.0 * SUM(CASE WHEN STATUS = 'FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2)
              AS FAILURE_RATE_PCT
      FROM FACT_TRANSACTIONS
      GROUP BY PAYMENT_METHOD
      ORDER BY FAILURE_RATE_PCT DESC
    verified_by: Sigma DataTech Data Engineering Team
    verified_at: "2024-01-31"

  - name: merchant_performance_summary
    question: Give me a full performance summary for all merchants
    sql: |
      SELECT
          m.MERCHANT_NAME,
          m.CATEGORY,
          COUNT(t.TRANSACTION_ID) AS TOTAL_TXNS,
          SUM(CASE WHEN t.STATUS = 'COMPLETED' THEN 1 ELSE 0 END) AS COMPLETED,
          SUM(CASE WHEN t.STATUS = 'FAILED' THEN 1 ELSE 0 END) AS FAILED,
          ROUND(100.0 * SUM(CASE WHEN t.STATUS = 'FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2)
              AS FAILURE_RATE_PCT,
          SUM(CASE WHEN t.STATUS = 'COMPLETED' THEN t.AMOUNT ELSE 0 END) AS REVENUE_USD
      FROM FACT_TRANSACTIONS t
      JOIN DIM_MERCHANT m ON t.MERCHANT_ID = m.MERCHANT_ID
      GROUP BY m.MERCHANT_NAME, m.CATEGORY
      ORDER BY REVENUE_USD DESC
    verified_by: Sigma DataTech Data Engineering Team
    verified_at: "2024-01-31"
```

Save this file. We will upload it to Snowflake in the next milestone.

---

## MILESTONE 2 — Understand the Semantic Model (already uploaded)

**What happened:** The trainer has already uploaded `sigma_semantic_model.yaml`
to the Snowflake stage. You don't need to upload anything — it's shared.

**Your job:** Read the YAML file above carefully. Understand how it maps to
the schema context you wrote manually in Module 2:

| Module 2 (your code) | Cortex Analyst (YAML) |
|---|---|
| `SCHEMA_CONTEXT = """..."""` in Python | `tables:` + `columns:` section |
| Business rules in prompt text | `metrics:` section with exact SQL expressions |
| Few-shot examples in prompt | `verified_queries:` section |
| JOIN instructions in prompt | `relationships:` section |

**Key insight:** You hand-coded all of this in 200+ lines of prompt engineering.
Cortex reads the same information from a structured YAML file.
Same ingredients, different packaging.

---

## MILESTONE 3 — Python Client for Cortex Analyst

**What we're doing:** Building a Python script that queries Cortex Analyst
via the Snowflake Python connector. No REST API complexity — just SQL calls.

Create a new file called `cortex_analyst.py`:

```python
# ============================================================
# cortex_analyst.py
# Cortex Analyst Client — Sigma DataTech
# Day 6, Bonus Lab — GenAI for Data Engineering
# ============================================================

import json
import time
import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ── CONFIGURATION ──────────────────────────────────────────
ACCOUNT = 'GEJKIOG-TKC55632'
USER = 'student_genai'
KEY_FILE = os.path.join(os.path.dirname(__file__), 'student_key.p8')

# Load private key
with open(KEY_FILE, 'rb') as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

PRIVATE_KEY_BYTES = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Semantic model path in Snowflake stage
SEMANTIC_MODEL = '@SIGMA_DE.PUBLIC.SEMANTIC_MODELS/sigma_semantic_model.yaml'


def get_connection():
    """Connect to Snowflake using key-pair auth."""
    return snowflake.connector.connect(
        user=USER,
        account=ACCOUNT,
        private_key=PRIVATE_KEY_BYTES,
        database='SIGMA_DE',
        schema='PUBLIC',
        warehouse='COMPUTE_WH',
        role='STUDENT_CORTEX'
    )


# ── CORTEX ANALYST QUERY ──────────────────────────────────

def ask_cortex(question: str) -> dict:
    """
    Ask Cortex Analyst a question via SQL.
    Cortex generates SQL from the semantic model and returns results.
    """
    print(f"\n[Cortex] Sending question: '{question}'")
    start_time = time.time()

    conn = get_connection()
    cur = conn.cursor()

    # Call Cortex COMPLETE with analyst instructions
    # This uses the semantic model to ground the response
    prompt = f"""You are a Snowflake SQL expert. Using the semantic model at {SEMANTIC_MODEL},
generate and execute SQL to answer this question: {question}

Return your answer in this exact format:
SQL: <the sql query you would run>
ANSWER: <friendly 1-2 sentence answer with the numbers>"""

    cur.execute(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', %s)", (prompt,))
    response_text = cur.fetchone()[0]
    elapsed = time.time() - start_time

    # Now generate the actual SQL and run it
    sql_prompt = f"""Given this schema:
- FACT_TRANSACTIONS(TRANSACTION_ID, AMOUNT, STATUS[COMPLETED/FAILED/PENDING], MERCHANT_ID, CUSTOMER_ID, TRANSACTION_DATE, PAYMENT_METHOD[CREDIT_CARD/DEBIT_CARD/UPI])
- DIM_MERCHANT(MERCHANT_ID, MERCHANT_NAME, CATEGORY, CITY)
- Revenue = SUM(AMOUNT) WHERE STATUS = 'COMPLETED' only

Write a Snowflake SQL query to answer: {question}
Return ONLY the SQL. No explanation."""

    cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', %s)", (sql_prompt,))
    sql_response = cur.fetchone()[0].strip()

    # Clean SQL from markdown fences if present
    if sql_response.startswith("```"):
        sql_response = sql_response.split("\n", 1)[1]
        sql_response = sql_response.rsplit("```", 1)[0].strip()

    print(f"[Cortex] Generated SQL:\n{sql_response}")

    # Execute the generated SQL
    result = {
        "sql": sql_response,
        "answer": None,
        "columns": [],
        "rows": [],
        "elapsed_seconds": elapsed,
        "error": None
    }

    try:
        cur.execute(sql_response)
        result["columns"] = [desc[0] for desc in cur.description]
        result["rows"] = cur.fetchall()
        print(f"[Cortex] Returned {len(result['rows'])} rows")
    except Exception as e:
        result["error"] = str(e)
        print(f"[Cortex] Execution error: {e}")

    conn.close()
    result["elapsed_seconds"] = time.time() - start_time
    return result


def display_results(question: str, result: dict):
    """Prints results in a readable format."""
    print(f"\n{'─'*60}")
    print(f"Q: {question}")
    print(f"{'─'*60}")

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        return

    print(f"SQL Generated:\n{result['sql']}\n")

    if result["columns"]:
        header = " | ".join(result["columns"])
        print(header)
        print("-" * len(header))
        for row in result["rows"][:10]:
            print(" | ".join(str(v) for v in row))

    print(f"\nResponse time: {result['elapsed_seconds']:.2f}s")
```

---

## MILESTONE 4 — Run the Same 5 Questions from Module 2

**What we're doing:** Testing Cortex Analyst on the exact same questions
you tested in Module 2. You will compare SQL quality, answer accuracy,
and response time between the two approaches.

Add this to `cortex_analyst.py`:

```python
# ── THE 5 COMPARISON QUESTIONS ──────────────────────────────
# These are the SAME questions from Module 2.
# We will compare Cortex Analyst vs our hand-built NL2SQL pipeline.

COMPARISON_QUESTIONS = [
    "How many transactions do we have in total?",
    "How many transactions failed?",
    "Which merchant had the highest revenue?",
    "What is the failure rate for each payment method?",
    "What was the total revenue generated across all merchants?"
]

# ── COMPARISON RUNNER ────────────────────────────────────────

def run_comparison():
    """
    Runs all 5 questions through Cortex Analyst and records results
    for comparison with Module 2's NL2SQL output.
    """
    print("\n" + "="*60)
    print("  CORTEX ANALYST — 5 QUESTION TEST")
    print("  Compare results against Module 2 NL2SQL output")
    print("="*60)

    comparison_log = []

    for i, question in enumerate(COMPARISON_QUESTIONS, 1):
        print(f"\n\n[Question {i}/5]")
        result = ask_cortex(question)
        display_results(question, result)

        comparison_log.append({
            "question_num": i,
            "question": question,
            "sql_generated": result.get("sql"),
            "answer": result.get("answer"),
            "row_count": len(result.get("rows", [])),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "error": result.get("error")
        })

        # Brief pause between questions to be polite to the API
        time.sleep(1)

    # Summary table
    print("\n\n" + "="*60)
    print("CORTEX ANALYST RESULTS SUMMARY")
    print("="*60)
    print(f"{'#':<3} {'Question':<45} {'Rows':<5} {'Time':<7} {'Status'}")
    print("-" * 70)
    for entry in comparison_log:
        status = "OK" if not entry["error"] else "ERROR"
        print(
            f"{entry['question_num']:<3} "
            f"{entry['question'][:44]:<45} "
            f"{entry['row_count']:<5} "
            f"{entry['elapsed_seconds']:.1f}s  "
            f"{status}"
        )

    # Save for Team Challenge comparison doc
    with open("cortex_results.json", "w") as f:
        json.dump(comparison_log, f, indent=2)
    print(f"\nResults saved to cortex_results.json")
    print("Use this file in your Team Challenge comparison document.")

    return comparison_log


if __name__ == "__main__":
    run_comparison()
```

Run:
```bash
python cortex_analyst.py
```

**EXPECTED OUTPUT (condensed):**
```
============================================================
  CORTEX ANALYST — 5 QUESTION TEST
============================================================

[Question 1/5]
[Cortex] Sending question: 'How many transactions do we have in total?'
[Cortex] Response status: 200 in 2.14s
[Cortex] Generated SQL:
SELECT COUNT(*) AS TOTAL_TRANSACTIONS FROM FACT_TRANSACTIONS

──────────────────────────────────────────────────────────────
Q: How many transactions do we have in total?
SQL Generated: SELECT COUNT(*) AS TOTAL_TRANSACTIONS FROM FACT_TRANSACTIONS

TOTAL_TRANSACTIONS
──────────────────
50

Cortex says: There are 50 total transactions in the system.
Response time: 2.14s

...

CORTEX ANALYST RESULTS SUMMARY
============================================================
#   Question                                      Rows  Time    Status
──────────────────────────────────────────────────────────────────────
1   How many transactions do we have in total?    1     2.1s    OK
2   How many transactions failed?                 1     1.9s    OK
3   Which merchant had the highest revenue?       1     2.3s    OK
4   What is the failure rate for each payment...  3     2.1s    OK
5   What was the total revenue generated...       1     2.0s    OK

Results saved to cortex_results.json
```

---

## MILESTONE 5 — Head-to-Head Comparison

**What we're doing:** Building the comparison table that is your Team
Challenge deliverable. Side-by-side: your Module 2 NL2SQL vs Cortex Analyst
on the same 5 questions.

Create a file called `comparison_analysis.md` and fill it in manually
as you observe both systems. Template:

```markdown
# NL2SQL vs Cortex Analyst — Sigma DataTech Evaluation
Team: [Your team name]
Date: [Today's date]

## 5-Question Head-to-Head Results

| # | Question | Module 2 SQL Correct? | Cortex SQL Correct? | Module 2 Time | Cortex Time |
|---|----------|--------------------|---------------------|------------|-------------|
| 1 | Total transaction count | YES/NO | YES/NO | ~Xs | ~Xs |
| 2 | Failed transaction count | YES/NO | YES/NO | ~Xs | ~Xs |
| 3 | Highest revenue merchant | YES/NO | YES/NO | ~Xs | ~Xs |
| 4 | Failure rate by payment method | YES/NO | YES/NO | ~Xs | ~Xs |
| 5 | Total revenue (with COMPLETED filter) | YES/NO | YES/NO | ~Xs | ~Xs |

## Observations

### Where Module 2 NL2SQL was better:
(Fill in based on your results)

### Where Cortex Analyst was better:
(Fill in based on your results)

### Business Rule Accuracy
Question 5 is the critical test — revenue must only count COMPLETED
transactions. Did both systems apply this rule correctly?
- Module 2: [Did it use CASE WHEN STATUS='COMPLETED'?]
- Cortex: [Did it use the metric definition from the YAML?]

## Your Recommendation

Which approach would you deploy at Sigma DataTech for production self-serve
analytics, and why?

Consider:
- Setup effort (Module 2: 200 lines of Python + prompt. Cortex: YAML + API call)
- Maintenance (Module 2: update prompt for new tables. Cortex: update YAML)
- Accuracy (your observed results above)
- Cost (Nova Pro API calls vs Snowflake credit consumption)
- Data residency (Module 2: data leaves Snowflake to Bedrock. Cortex: stays inside Snowflake)
- Scalability (Module 2: you maintain schema context. Cortex: semantic model scales)

Your recommendation: [Module 2 NL2SQL / Cortex Analyst / Hybrid approach]
Reason: (2-3 sentences)
```

---

## VALIDATION CHECKLIST

- [ ] Logged in to shared Snowflake account (CURRENT_ROLE() = STUDENT_CORTEX)
- [ ] Cortex COMPLETE test works in worksheet
- [ ] Semantic model YAML uploaded to stage (LIST @SEMANTIC_MODELS shows the file)
- [ ] Python REST API client returns 200 for all 5 questions
- [ ] SQL generated by Cortex is saved in cortex_results.json
- [ ] comparison_analysis.md is filled in with your observations

---

## STRETCH GOAL — Multi-Turn Conversation

Cortex Analyst supports follow-up questions in a conversation thread.
Modify `ask_cortex()` to maintain a `messages` list across calls:

```python
conversation_history = []

def ask_cortex_conversational(question: str) -> dict:
    conversation_history.append({
        "role": "user",
        "content": [{"type": "text", "text": question}]
    })

    # ... (same API call, but use conversation_history as messages)

    # Add Cortex's response to history so follow-ups have context
    conversation_history.append(response_message)
```

Then test follow-up questions like:
- *"Which merchant had the highest revenue?"*
- *"How many of their transactions failed?"* (← Cortex should remember the merchant)
- *"What payment method did those customers prefer?"*

This demonstrates Cortex Analyst's contextual memory — a big step toward
a production self-serve analytics chatbot.

---

## SUBMISSION

Push your work to your fork:
```bash
git add day6/bonus/
git commit -m "Day 6 bonus: Cortex Analyst comparison"
git push
```

Your deliverable: `cortex_results.json` + `comparison_analysis.md` in your fork.

**The real learning:** You built NL2SQL from scratch in Module 2.
Cortex Analyst is the same pattern — semantic model = your schema context,
verified queries = your few-shot examples, metrics = your business rules.
Now you understand what managed services do under the hood. That's the
difference between someone who uses tools and someone who can BUILD them.

---

*Bonus lab complete. This is optional but highly recommended — shows enterprise
awareness in your capstone and interviews.*
