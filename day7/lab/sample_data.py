"""
Day 7 — Sample Data (Complete — no TODOs here)
Pipeline spec, sample transactions, merchant data, schemas, and DAG config
for the Pipeline Brain modules.
"""

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE SPEC — fed to AI in Modules 1, 2, 3
# This is what a senior DE writes. AI turns it into working code.
# ══════════════════════════════════════════════════════════════════════════════

PIPELINE_SPEC = """PIPELINE SPEC: Sigma DataTech Transaction Analytics Pipeline
Version: 1.0 | Author: Data Engineering Team | Date: 2026-05-27

OBJECTIVE:
Build a daily batch pipeline that transforms raw transaction data into
business-ready analytics tables using a Bronze -> Silver -> Gold medallion architecture.

DATA SOURCES:
- Raw CSV files: transactions.csv, merchants.csv (one file per day)
- Volume: ~50,000 transactions/day, ~500 merchants (slowly changing dimension)
- Frequency: Daily batch at 02:00 UTC

BRONZE LAYER (raw ingest):
- Read raw CSV with all columns as strings (preserve original data exactly)
- Add metadata columns: ingestion_timestamp, source_file, pipeline_run_id
- Write as Parquet partitioned by date
- No transformations -- raw data only, no filtering

SILVER LAYER (clean + enrich):
- Cast columns to correct types: amount -> float, transaction_date -> date, all IDs -> string
- Filter: remove records where transaction_id is NULL or amount < 0
- Deduplicate: if same transaction_id appears twice, keep the record with latest ingestion_timestamp
- Enrich: join transactions with merchants on merchant_id to get merchant_name, category, city
- Add quality flag: mark records with no matching merchant as 'UNMATCHED'
- Write as Parquet partitioned by date

GOLD LAYER (business aggregates -- 3 tables):
Table 1 -- merchant_performance: daily revenue and transaction counts per merchant
  Columns: merchant_id, merchant_name, category, city, date,
           total_revenue (COMPLETED only), txn_count, failure_rate_pct

Table 2 -- customer_ltv: lifetime value summary per customer
  Columns: customer_id, total_spent, total_txns, avg_txn_value,
           first_txn_date, last_txn_date, preferred_payment_method

Table 3 -- daily_summary: one row per day across all merchants
  Columns: date, total_revenue, total_txns, unique_customers,
           unique_merchants, failure_rate_pct

BUSINESS RULES:
- Revenue = SUM(amount) WHERE status = 'COMPLETED' only
- Failure rate = COUNT(status='FAILED') / COUNT(*) * 100
- Partition all output tables by date
- Idempotent: re-running for same date must OVERWRITE existing partition, never append

ERROR HANDLING:
- If source file missing: log warning, skip day, do not crash
- If more than 5% of records fail quality checks: halt pipeline, log error, do not write Silver
- Log all row counts at each stage: input, after filter, after dedup, output
- Write run metadata summary to a JSON file after each run

PERFORMANCE:
- Use partition pruning on date column for all reads
- Cache merchant dimension table (small, ~500 rows, referenced multiple times)
- Broadcast merchant join (small dimension side)
"""

# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE DATA — Sigma DataTech transaction universe
# Date range: 2024-01-15 to 2024-01-31
# ══════════════════════════════════════════════════════════════════════════════

SAMPLE_TRANSACTIONS = [
    {"transaction_id": "TXN001", "amount": 450.00, "status": "COMPLETED",  "merchant_id": "M001", "customer_id": "C001", "transaction_date": "2024-01-15", "payment_method": "UPI"},
    {"transaction_id": "TXN002", "amount": 1200.50,"status": "COMPLETED",  "merchant_id": "M002", "customer_id": "C002", "transaction_date": "2024-01-15", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN003", "amount": 89.00,  "status": "FAILED",     "merchant_id": "M003", "customer_id": "C003", "transaction_date": "2024-01-16", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN004", "amount": 3200.00,"status": "COMPLETED",  "merchant_id": "M004", "customer_id": "C001", "transaction_date": "2024-01-16", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN005", "amount": 250.00, "status": "PENDING",    "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN006", "amount": 175.50, "status": "COMPLETED",  "merchant_id": "M005", "customer_id": "C002", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN007", "amount": 540.00, "status": "FAILED",     "merchant_id": "M006", "customer_id": "C005", "transaction_date": "2024-01-18", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN008", "amount": 890.00, "status": "COMPLETED",  "merchant_id": "M002", "customer_id": "C003", "transaction_date": "2024-01-18", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN009", "amount": 65.00,  "status": "COMPLETED",  "merchant_id": "M007", "customer_id": "C006", "transaction_date": "2024-01-19", "payment_method": "UPI"},
    {"transaction_id": "TXN010", "amount": 1450.00,"status": "COMPLETED",  "merchant_id": "M008", "customer_id": "C001", "transaction_date": "2024-01-19", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN011", "amount": -50.00, "status": "FAILED",     "merchant_id": "M003", "customer_id": "C007", "transaction_date": "2024-01-20", "payment_method": "DEBIT_CARD"},  # bad: negative amount
    {"transaction_id": None,     "amount": 320.00, "status": "COMPLETED",  "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-20", "payment_method": "UPI"},          # bad: null ID
    {"transaction_id": "TXN012", "amount": 780.00, "status": "COMPLETED",  "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN013", "amount": 220.00, "status": "FAILED",     "merchant_id": "M005", "customer_id": "C008", "transaction_date": "2024-01-22", "payment_method": "UPI"},
    {"transaction_id": "TXN014", "amount": 990.00, "status": "COMPLETED",  "merchant_id": "M006", "customer_id": "C003", "transaction_date": "2024-01-23", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN015", "amount": 125.00, "status": "PENDING",    "merchant_id": "M007", "customer_id": "C005", "transaction_date": "2024-01-24", "payment_method": "UPI"},
    {"transaction_id": "TXN012", "amount": 780.00, "status": "COMPLETED",  "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},  # duplicate — same TXN012
    {"transaction_id": "TXN016", "amount": 3400.00,"status": "COMPLETED",  "merchant_id": "M008", "customer_id": "C006", "transaction_date": "2024-01-25", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN017", "amount": 145.00, "status": "FAILED",     "merchant_id": "MXXX", "customer_id": "C009", "transaction_date": "2024-01-28", "payment_method": "DEBIT_CARD"},  # unmatched merchant
    {"transaction_id": "TXN018", "amount": 560.00, "status": "COMPLETED",  "merchant_id": "M001", "customer_id": "C007", "transaction_date": "2024-01-31", "payment_method": "UPI"},
]

SAMPLE_MERCHANTS = [
    {"merchant_id": "M001", "merchant_name": "Swiggy",      "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M002", "merchant_name": "Amazon",       "category": "E-Commerce",    "city": "Bengaluru"},
    {"merchant_id": "M003", "merchant_name": "Zomato",       "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M004", "merchant_name": "Ola",          "category": "Travel",        "city": "Bengaluru"},
    {"merchant_id": "M005", "merchant_name": "BigBasket",    "category": "Grocery",       "city": "Bengaluru"},
    {"merchant_id": "M006", "merchant_name": "BookMyShow",   "category": "Entertainment", "city": "Mumbai"},
    {"merchant_id": "M007", "merchant_name": "MakeMyTrip",   "category": "Travel",        "city": "Gurugram"},
    {"merchant_id": "M008", "merchant_name": "Flipkart",     "category": "E-Commerce",    "city": "Bengaluru"},
]

# ══════════════════════════════════════════════════════════════════════════════
# SCHEMAS — used in Module 4 (schema drift simulation)
# ══════════════════════════════════════════════════════════════════════════════

SCHEMA_BRONZE = {
    "transaction_id":      "string",
    "amount":              "string",   # raw CSV — everything is string at Bronze
    "status":              "string",
    "merchant_id":         "string",
    "customer_id":         "string",
    "transaction_date":    "string",
    "payment_method":      "string",
    "ingestion_timestamp": "string",
    "source_file":         "string",
    "pipeline_run_id":     "string",
}

SCHEMA_SILVER = {
    "transaction_id":      "string",
    "amount":              "float",
    "status":              "string",
    "merchant_id":         "string",
    "customer_id":         "string",
    "transaction_date":    "date",
    "payment_method":      "string",
    "merchant_name":       "string",   # enriched from dim
    "category":            "string",   # enriched from dim
    "city":                "string",   # enriched from dim
    "quality_flag":        "string",   # CLEAN or UNMATCHED
    "ingestion_timestamp": "timestamp",
    "pipeline_run_id":     "string",
}

# ══════════════════════════════════════════════════════════════════════════════
# DAG CONFIG — read by Module 2 (dag_generator)
# ══════════════════════════════════════════════════════════════════════════════

DAG_CONFIG = {
    "dag_id":     "sigma_transaction_pipeline",
    "schedule":   "0 2 * * *",          # daily at 02:00 UTC
    "start_date": "2024-01-01",
    "catchup":    False,
    "retries":    2,
    "retry_delay_minutes": 5,
    "email_on_failure": True,
    "sla_miss_minutes": 120,            # 2-hour SLA window
    "tags":       ["sigma", "transactions", "daily"],
    "description": "Daily Bronze->Silver->Gold pipeline for Sigma DataTech transactions",
}
