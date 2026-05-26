"""
Day 6 — Sample Data (Complete — no TODOs here)
Schema context, broken queries, and test data for all modules.
"""

# ── SCHEMA CONTEXT ──────────────────────────────────────────
# Compact notation — used in review prompts for token efficiency

SCHEMA_COMPACT = """sigma_analytics.fact_transactions(
    transaction_id VARCHAR PK,
    amount DECIMAL(10,2) -- always USD,
    status VARCHAR -- COMPLETED, FAILED, PENDING,
    merchant_id VARCHAR FK->dim_merchant,
    customer_id VARCHAR FK->dim_customer,
    transaction_date DATE,
    payment_method VARCHAR -- CREDIT_CARD, DEBIT_CARD, UPI
)

sigma_analytics.dim_merchant(
    merchant_id VARCHAR PK,
    merchant_name VARCHAR,
    category VARCHAR -- Food Delivery, E-Commerce, Entertainment, Travel, Grocery,
    city VARCHAR,
    onboarded_date DATE
)

sigma_analytics.dim_customer(
    customer_id VARCHAR PK,
    customer_name VARCHAR,
    email VARCHAR,
    tier VARCHAR -- GOLD, SILVER, BRONZE,
    signup_date DATE,
    city VARCHAR
)

BUSINESS RULES:
- Revenue = SUM(amount) WHERE status = 'COMPLETED' only
- Failure rate = COUNT(FAILED) / COUNT(*) * 100
- When showing merchant names, always JOIN dim_merchant (don't show IDs)
"""

# ── RICH SCHEMA CONTEXT (for NL2SQL — more detail = more accuracy) ─────

SCHEMA_RICH = """
=== SIGMA DATATECH SNOWFLAKE SCHEMA ===
Database: SIGMA_DE | Schema: PUBLIC

TABLE: FACT_TRANSACTIONS
  TRANSACTION_ID   VARCHAR(50)   PK    -- e.g. TXN001
  AMOUNT           DECIMAL(10,2)       -- Always USD. Includes ALL statuses.
  STATUS           VARCHAR(20)         -- COMPLETED, FAILED, or PENDING
  MERCHANT_ID      VARCHAR(50)         -- FK -> DIM_MERCHANT.MERCHANT_ID
  CUSTOMER_ID      VARCHAR(50)         -- e.g. CUST_001
  TRANSACTION_DATE DATE                -- Date only (not timestamp)
  PAYMENT_METHOD   VARCHAR(30)         -- CREDIT_CARD, DEBIT_CARD, or UPI

TABLE: DIM_MERCHANT
  MERCHANT_ID    VARCHAR(50)   PK    -- e.g. MERCH_001
  MERCHANT_NAME  VARCHAR(100)        -- Human name e.g. 'Swiggy'
  CATEGORY       VARCHAR(50)         -- Food Delivery, E-Commerce, Entertainment, Travel, Grocery
  CITY           VARCHAR(50)         -- HQ city e.g. 'Bengaluru'

=== JOIN RELATIONSHIPS ===
FACT_TRANSACTIONS.MERCHANT_ID = DIM_MERCHANT.MERCHANT_ID (MANY-TO-ONE)

=== BUSINESS RULES (FOLLOW EXACTLY) ===
RULE 1: Revenue = SUM(AMOUNT) WHERE STATUS = 'COMPLETED' only.
        FAILED and PENDING are NOT revenue.
RULE 2: Failure rate = COUNT(FAILED) / COUNT(*) * 100 as percentage.
RULE 3: When user asks for merchant names, always JOIN DIM_MERCHANT.
RULE 4: For "top N" queries, use ORDER BY ... DESC LIMIT N.
RULE 5: Date range in data: 2024-01-15 to 2024-01-31.

=== FEW-SHOT EXAMPLES (style guide) ===
Q: How many transactions failed?
SQL: SELECT COUNT(*) AS FAILED_COUNT FROM FACT_TRANSACTIONS WHERE STATUS = 'FAILED';

Q: Which merchant had the highest revenue?
SQL:
SELECT m.MERCHANT_NAME,
       SUM(CASE WHEN t.STATUS='COMPLETED' THEN t.AMOUNT ELSE 0 END) AS REVENUE_USD
FROM FACT_TRANSACTIONS t
JOIN DIM_MERCHANT m ON t.MERCHANT_ID = m.MERCHANT_ID
GROUP BY m.MERCHANT_NAME
ORDER BY REVENUE_USD DESC
LIMIT 1;

Q: What is the failure rate by payment method?
SQL:
SELECT PAYMENT_METHOD,
       COUNT(*) AS TOTAL,
       SUM(CASE WHEN STATUS='FAILED' THEN 1 ELSE 0 END) AS FAILED,
       ROUND(100.0 * SUM(CASE WHEN STATUS='FAILED' THEN 1 ELSE 0 END) / COUNT(*), 2) AS FAILURE_RATE_PCT
FROM FACT_TRANSACTIONS
GROUP BY PAYMENT_METHOD
ORDER BY FAILURE_RATE_PCT DESC;
"""

# ── BROKEN QUERIES (for Module 1 — SQL Review) ────────────

BROKEN_QUERIES = {
    "revenue_by_merchant": {
        "sql": """SELECT m.merchant_name,
       SUM(t.amount) as total_revenue,
       COUNT(*) as txn_count
FROM fact_transactions t, dim_merchant m
WHERE t.merchant_id = m.merchant_id
AND t.transaction_date > '2024-01-01'
GROUP BY m.merchant_name
ORDER BY total_revenue
LIMIT 10;""",
        "known_bugs": [
            "Implicit JOIN (FROM a, b WHERE) — performance anti-pattern",
            "No STATUS='COMPLETED' filter — includes FAILED in revenue",
            "ORDER BY ascending — should be DESC for 'top 10'",
        ],
    },
    "customer_spend": {
        "sql": """SELECT c.customer_name, c.email, c.tier,
       SUM(t.amount) as lifetime_value,
       COUNT(t.transaction_id) as total_orders
FROM dim_customer c
LEFT JOIN fact_transactions t ON c.customer_id = t.customer_id
WHERE t.status = 'COMPLETED'
GROUP BY c.customer_name, c.email
HAVING SUM(t.amount) > 1000
ORDER BY lifetime_value DESC;""",
        "known_bugs": [
            "LEFT JOIN + WHERE on right table = INNER JOIN (drops 0-order customers)",
            "GROUP BY missing c.tier — will fail in Snowflake/PG",
            "Selecting email — PII exposure risk",
            "No date filter — full table scan on large data",
        ],
    },
    "daily_failure_rate": {
        "sql": """SELECT transaction_date,
       (SELECT COUNT(*) FROM fact_transactions f2
        WHERE f2.status = 'FAILED'
        AND f2.transaction_date = t.transaction_date) as failed_count,
       COUNT(*) as total_count,
       failed_count / total_count * 100 as failure_rate
FROM fact_transactions t
GROUP BY transaction_date
ORDER BY transaction_date;""",
        "known_bugs": [
            "Correlated subquery — runs per group, extremely slow at scale",
            "Cannot reference alias in same SELECT — query will error",
            "Integer division — gives 0 for any rate under 100%",
        ],
    },
}

# ── NL2SQL TEST QUESTIONS (for Module 2) ───────────────────

NL2SQL_QUESTIONS = [
    "How many transactions do we have in total?",
    "How many transactions failed?",
    "Which merchant had the highest revenue?",
    "What is the failure rate for each payment method?",
    "What was the total revenue generated across all merchants?",
]

# ── SNOWFLAKE CONFIG TEMPLATE ──────────────────────────────

SNOWFLAKE_CONFIG_TEMPLATE = {
    "user": "student_genai",
    "account": "GEJKIOG-TKC55632",
    "private_key_path": "../bonus/student_key.p8",
    "database": "SIGMA_DE",
    "schema": "PUBLIC",
    "warehouse": "COMPUTE_WH",
    "role": "STUDENT_CORTEX",
}
