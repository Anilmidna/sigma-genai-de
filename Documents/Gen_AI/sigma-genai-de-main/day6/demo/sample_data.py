"""
Day 6 — SQL Brain Lab: Sample data, broken queries, and schemas.
Sigma DataTech GenAI for DE Bootcamp.
"""

# Schema for Sigma DataTech's analytics warehouse
SIGMA_SCHEMA = """-- Sigma DataTech Analytics Warehouse (Snowflake)
-- This is a simplified production schema representing e-commerce + fintech data

CREATE TABLE sigma_analytics.fact_transactions (
    transaction_id   VARCHAR(50)   PRIMARY KEY,
    amount           DECIMAL(10,2) NOT NULL,
    status           VARCHAR(20)   NOT NULL,  -- COMPLETED, FAILED, PENDING
    merchant_id      VARCHAR(50)   NOT NULL,
    customer_id      VARCHAR(50)   NOT NULL,
    transaction_date DATE          NOT NULL,
    payment_method   VARCHAR(30)   NOT NULL   -- CREDIT_CARD, DEBIT_CARD, UPI
);

CREATE TABLE sigma_analytics.dim_merchant (
    merchant_id    VARCHAR(50)  PRIMARY KEY,
    merchant_name  VARCHAR(100) NOT NULL,
    category       VARCHAR(50)  NOT NULL,     -- Food Delivery, E-Commerce, etc.
    city           VARCHAR(50)  NOT NULL,
    onboarded_date DATE         NOT NULL
);

CREATE TABLE sigma_analytics.dim_customer (
    customer_id   VARCHAR(50)  PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    email         VARCHAR(200) NOT NULL,
    tier          VARCHAR(20)  NOT NULL,      -- GOLD, SILVER, BRONZE
    signup_date   DATE         NOT NULL,
    city          VARCHAR(50)  NOT NULL
);

CREATE TABLE sigma_analytics.fact_daily_metrics (
    metric_date     DATE         NOT NULL,
    merchant_id     VARCHAR(50)  NOT NULL,
    total_txns      INT          NOT NULL,
    total_amount    DECIMAL(12,2) NOT NULL,
    failed_txns     INT          NOT NULL,
    avg_txn_value   DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (metric_date, merchant_id)
);
"""

SIGMA_SCHEMA_COMPACT = """sigma_analytics.fact_transactions(transaction_id PK, amount DECIMAL, status VARCHAR[COMPLETED/FAILED/PENDING], merchant_id FK, customer_id FK, transaction_date DATE, payment_method VARCHAR[CREDIT_CARD/DEBIT_CARD/UPI])
sigma_analytics.dim_merchant(merchant_id PK, merchant_name, category, city, onboarded_date DATE)
sigma_analytics.dim_customer(customer_id PK, customer_name, email, tier[GOLD/SILVER/BRONZE], signup_date DATE, city)
sigma_analytics.fact_daily_metrics(metric_date DATE, merchant_id FK, total_txns INT, total_amount DECIMAL, failed_txns INT, avg_txn_value DECIMAL) PK=(metric_date,merchant_id)"""

# Broken SQL queries for the review lab
BROKEN_QUERIES = {
    "Revenue by Merchant (3 bugs)": {
        "sql": """SELECT m.merchant_name,
       SUM(t.amount) as total_revenue,
       COUNT(*) as txn_count
FROM fact_transactions t, dim_merchant m
WHERE t.merchant_id = m.merchant_id
AND t.transaction_date > '2024-01-01'
GROUP BY m.merchant_name
ORDER BY total_revenue
LIMIT 10;""",
        "bugs": [
            "BUG 1 (Performance): Uses implicit JOIN (FROM a, b WHERE) instead of explicit JOIN. Harder to read, error-prone with more tables.",
            "BUG 2 (Logic): No status filter — includes FAILED and PENDING transactions in 'revenue'. Revenue should only count COMPLETED.",
            "BUG 3 (Logic): ORDER BY total_revenue is ascending by default. Top 10 by revenue needs DESC.",
        ],
        "severity": "Medium — produces wrong numbers silently (worst kind of bug)",
    },
    "Customer Spend Analysis (4 bugs)": {
        "sql": """SELECT c.customer_name, c.email, c.tier,
       SUM(t.amount) as lifetime_value,
       COUNT(t.transaction_id) as total_orders
FROM dim_customer c
LEFT JOIN fact_transactions t ON c.customer_id = t.customer_id
WHERE t.status = 'COMPLETED'
GROUP BY c.customer_name, c.email
HAVING SUM(t.amount) > 1000
ORDER BY lifetime_value DESC;""",
        "bugs": [
            "BUG 1 (Logic): LEFT JOIN + WHERE on right table = effectively INNER JOIN. Customers with 0 transactions are silently dropped.",
            "BUG 2 (SQL Error): GROUP BY is missing c.tier — query will fail in Snowflake/PostgreSQL (only MySQL allows this).",
            "BUG 3 (Security): Selecting email in a query that might be used for dashboards — potential PII exposure.",
            "BUG 4 (Performance): No date filter — scans entire transaction history. On 100M+ rows, this is very slow.",
        ],
        "severity": "High — silently drops data AND has a PII risk",
    },
    "Daily Failure Rate (2 bugs + 1 anti-pattern)": {
        "sql": """SELECT transaction_date,
       (SELECT COUNT(*) FROM fact_transactions f2
        WHERE f2.status = 'FAILED'
        AND f2.transaction_date = t.transaction_date) as failed_count,
       COUNT(*) as total_count,
       failed_count / total_count * 100 as failure_rate
FROM fact_transactions t
GROUP BY transaction_date
ORDER BY transaction_date;""",
        "bugs": [
            "BUG 1 (Performance Anti-Pattern): Correlated subquery runs once PER GROUP. On 365 days × 1M rows = extremely slow. Use CASE WHEN + SUM instead.",
            "BUG 2 (SQL Error): Cannot reference alias 'failed_count' in the same SELECT level. Must use a CTE or repeat the expression.",
            "ANTI-PATTERN: Integer division (failed_count / total_count) returns 0 for any rate < 100%. Need CAST to FLOAT or multiply by 100.0.",
        ],
        "severity": "Critical — query won't even run, and if fixed naively, gives 0% for all rates",
    },
}

# NL2SQL examples for the generation lab
NL2SQL_EXAMPLES = [
    "Show me top 5 merchants by total revenue in January 2024",
    "Which customers had more than 3 failed transactions?",
    "What's the daily transaction count trend for UPI payments?",
    "Find gold-tier customers in Bengaluru who haven't transacted in 30 days",
    "Compare average transaction value across payment methods for completed orders",
    "Show merchants with failure rate above 20% in the last 7 days",
]

# dbt project scaffold expectations
DBT_PROJECT_STRUCTURE = """
dbt project structure we're generating:
  sigma_dbt/
  ├── models/
  │   ├── staging/
  │   │   └── stg_transactions.sql        (clean + typed from raw)
  │   ├── intermediate/
  │   │   └── int_merchant_daily_metrics.sql  (aggregated daily)
  │   └── marts/
  │       └── mart_merchant_performance.sql   (final business table)
  ├── models/staging/schema.yml            (sources + column docs)
  ├── models/marts/schema.yml              (tests: not_null, unique, accepted_values)
  └── dbt_project.yml
"""

# Test scenarios for dbt test generation
DBT_TEST_SCENARIOS = {
    "not_null on critical columns": {
        "description": "Ensures no NULL values in business-critical columns",
        "example": """- name: not_null_transaction_id
  columns:
    - name: transaction_id
      tests:
        - not_null""",
    },
    "unique on primary keys": {
        "description": "Validates no duplicate records (data integrity)",
        "example": """- name: unique_transaction_id
  columns:
    - name: transaction_id
      tests:
        - unique""",
    },
    "accepted_values for enums": {
        "description": "Catches unexpected values (e.g., new status types)",
        "example": """- name: valid_status_values
  columns:
    - name: status
      tests:
        - accepted_values:
            values: ['COMPLETED', 'FAILED', 'PENDING']""",
    },
    "relationships (referential integrity)": {
        "description": "Ensures foreign keys point to real records",
        "example": """- name: valid_merchant_fk
  columns:
    - name: merchant_id
      tests:
        - relationships:
            to: ref('stg_merchants')
            field: merchant_id""",
    },
}
