"""
Day 9 — Shared Sample Data
Sigma DataTech transaction dataset with pre-seeded traps for all 9 teams.
"""

# ── Core transactions (clean) ─────────────────────────────────────────────────
TRANSACTIONS_CLEAN = [
    {"transaction_id": "TXN001", "amount": 450.00,   "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C001", "transaction_date": "2024-01-15", "payment_method": "UPI"},
    {"transaction_id": "TXN002", "amount": 1200.50,  "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C002", "transaction_date": "2024-01-15", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN003", "amount": 89.00,    "status": "FAILED",    "merchant_id": "M003", "customer_id": "C003", "transaction_date": "2024-01-16", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN004", "amount": 3200.00,  "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C001", "transaction_date": "2024-01-16", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN005", "amount": 250.00,   "status": "PENDING",   "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN006", "amount": 175.50,   "status": "COMPLETED", "merchant_id": "M005", "customer_id": "C002", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN007", "amount": 540.00,   "status": "FAILED",    "merchant_id": "M006", "customer_id": "C005", "transaction_date": "2024-01-18", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN008", "amount": 890.00,   "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C003", "transaction_date": "2024-01-18", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN009", "amount": 65.00,    "status": "COMPLETED", "merchant_id": "M007", "customer_id": "C006", "transaction_date": "2024-01-19", "payment_method": "UPI"},
    {"transaction_id": "TXN010", "amount": 1450.00,  "status": "COMPLETED", "merchant_id": "M008", "customer_id": "C001", "transaction_date": "2024-01-19", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN012", "amount": 780.00,   "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN014", "amount": 990.00,   "status": "COMPLETED", "merchant_id": "M006", "customer_id": "C003", "transaction_date": "2024-01-23", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN016", "amount": 3400.00,  "status": "COMPLETED", "merchant_id": "M008", "customer_id": "C006", "transaction_date": "2024-01-25", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN018", "amount": 560.00,   "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C007", "transaction_date": "2024-01-31", "payment_method": "UPI"},
]

# ── Dirty transactions (with quality issues — traps are here) ─────────────────
# TRAP T1 (Team 1 — Fraud Hunter): TXN020 has a future date (2099) — impossible
# TRAP T2 (Team 2 — Data Therapist): TXN011 is negative — refund or fraud?
# TRAP T2b: TXN012 appears in BOTH clean and dirty — duplicate across source files
# TRAP T4 (Team 4 — CFO): TXN019 is ₹0 COMPLETED — statistically invisible but wrong
# TRAP T6 (Team 6 — Incident): TXN012 duplicate will cause PK violation on Silver insert
TRANSACTIONS_DIRTY = [
    {"transaction_id": None,     "amount": 320.00,    "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-20", "payment_method": "UPI"},
    {"transaction_id": "TXN011", "amount": -50.00,    "status": "FAILED",    "merchant_id": "M003", "customer_id": "C007", "transaction_date": "2024-01-20", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN012", "amount": 780.00,    "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},  # duplicate of clean TXN012
    {"transaction_id": "TXN017", "amount": 145.00,    "status": "FAILED",    "merchant_id": "MXXX", "customer_id": "C009", "transaction_date": "2024-01-28", "payment_method": "DEBIT_CARD"},   # unmatched merchant
    {"transaction_id": "TXN019", "amount": 0.00,      "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C001", "transaction_date": "2024-01-29", "payment_method": "UPI"},           # zero amount
    {"transaction_id": "TXN020", "amount": 99999.99,  "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C010", "transaction_date": "2099-12-31", "payment_method": "CREDIT_CARD"},   # future date — impossible
    {"transaction_id": "TXN015", "amount": 125.00,    "status": "PENDING",   "merchant_id": "M007", "customer_id": "C005", "transaction_date": "2024-01-24", "payment_method": "UPI"},
]

# ── Synthetic data for Team 8 — statistically valid but domain-impossible ─────
# TRAP T8a: UPI amount > ₹100,000 (UPI daily limit in India)
# TRAP T8b: Future date transaction
# TRAP T8c: Status "APPROVED" — not in valid set (COMPLETED/FAILED/PENDING)
# TRAP T8d: Merchant M009 doesn't exist in merchants table
# TRAP T8e: ₹0 COMPLETED — zero-value success
SYNTHETIC_TRANSACTIONS = [
    {"transaction_id": "SYN001", "amount": 520.00,    "status": "COMPLETED", "merchant_id": "M001", "customer_id": "CS01", "transaction_date": "2024-01-15", "payment_method": "UPI"},
    {"transaction_id": "SYN002", "amount": 1150.00,   "status": "COMPLETED", "merchant_id": "M002", "customer_id": "CS02", "transaction_date": "2024-01-16", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "SYN003", "amount": 95.00,     "status": "FAILED",    "merchant_id": "M003", "customer_id": "CS03", "transaction_date": "2024-01-17", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "SYN004", "amount": 150000.00, "status": "COMPLETED", "merchant_id": "M001", "customer_id": "CS04", "transaction_date": "2024-01-18", "payment_method": "UPI"},           # TRAP: UPI > ₹1L
    {"transaction_id": "SYN005", "amount": 340.00,    "status": "APPROVED",  "merchant_id": "M005", "customer_id": "CS05", "transaction_date": "2024-01-19", "payment_method": "UPI"},           # TRAP: invalid status
    {"transaction_id": "SYN006", "amount": 870.00,    "status": "COMPLETED", "merchant_id": "M009", "customer_id": "CS06", "transaction_date": "2024-01-20", "payment_method": "CREDIT_CARD"},   # TRAP: merchant doesn't exist
    {"transaction_id": "SYN007", "amount": 0.00,      "status": "COMPLETED", "merchant_id": "M002", "customer_id": "CS07", "transaction_date": "2024-01-21", "payment_method": "DEBIT_CARD"},    # TRAP: zero amount
    {"transaction_id": "SYN008", "amount": 430.00,    "status": "FAILED",    "merchant_id": "M006", "customer_id": "CS08", "transaction_date": "2099-06-15", "payment_method": "CREDIT_CARD"},   # TRAP: future date
    {"transaction_id": "SYN009", "amount": 1800.00,   "status": "COMPLETED", "merchant_id": "M008", "customer_id": "CS09", "transaction_date": "2024-01-23", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "SYN010", "amount": 290.00,    "status": "PENDING",   "merchant_id": "M007", "customer_id": "CS10", "transaction_date": "2024-01-24", "payment_method": "UPI"},
]

# ── Merchants ─────────────────────────────────────────────────────────────────
MERCHANTS = [
    {"merchant_id": "M001", "merchant_name": "Swiggy",       "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M002", "merchant_name": "Amazon",       "category": "E-Commerce",    "city": "Bengaluru"},
    {"merchant_id": "M003", "merchant_name": "Zomato",       "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M004", "merchant_name": "Ola",          "category": "Travel",        "city": "Bengaluru"},
    {"merchant_id": "M005", "merchant_name": "BigBasket",    "category": "Grocery",       "city": "Bengaluru"},
    {"merchant_id": "M006", "merchant_name": "BookMyShow",   "category": "Entertainment", "city": "Mumbai"},
    {"merchant_id": "M007", "merchant_name": "MakeMyTrip",   "category": "Travel",        "city": "Gurugram"},
    {"merchant_id": "M008", "merchant_name": "Flipkart",     "category": "E-Commerce",    "city": "Bengaluru"},
]

# ── Schema versions for Team 7 (Schema Archaeologist) ────────────────────────
SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS txn_v1 (
    transaction_id VARCHAR PRIMARY KEY,
    amount         DOUBLE NOT NULL,
    status         VARCHAR NOT NULL,
    merchant_id    VARCHAR,
    transaction_date DATE
);
"""

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS txn_v2 (
    transaction_id VARCHAR PRIMARY KEY,
    amount         DOUBLE NOT NULL,
    status         VARCHAR NOT NULL,
    merchant_id    VARCHAR,
    customer_id    VARCHAR,
    transaction_date  DATE,
    payment_method VARCHAR
);
"""

# TRAP T7: payment_method column REMOVED in v3 — silently breaks all UPI queries downstream
SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS txn_v3 (
    transaction_id VARCHAR PRIMARY KEY,
    amount         DOUBLE NOT NULL,
    status         VARCHAR NOT NULL,
    merchant_id    VARCHAR,
    user_id        VARCHAR,
    transaction_date DATE
);
"""

MIGRATION_V1_TO_V2 = """
ALTER TABLE txn_v1 ADD COLUMN customer_id VARCHAR;
ALTER TABLE txn_v1 ADD COLUMN payment_method VARCHAR;
-- Rename table: CREATE TABLE txn_v2 AS SELECT * FROM txn_v1; DROP TABLE txn_v1;
"""

# TRAP: This migration drops payment_method entirely — any downstream UPI filter silently returns 0 rows
MIGRATION_V2_TO_V3 = """
ALTER TABLE txn_v2 RENAME COLUMN customer_id TO user_id;
ALTER TABLE txn_v2 DROP COLUMN payment_method;
-- Rename table: CREATE TABLE txn_v3 AS SELECT * FROM txn_v2; DROP TABLE txn_v2;
"""

# ── Pipeline versions for Team 3 (Pipeline Lawyer) ───────────────────────────
PIPELINE_V1_CODE = '''
def load_silver(rows):
    """Load rows into Silver table."""
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        con.execute(
            "INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )

def main():
    bronze = fetch_bronze()
    silver = transform(bronze)
    load_silver(silver)
'''

# TRAP T3: seen_ids is a module-level global — second call to run_pipeline() in same
# session silently skips ALL transactions already processed (appears to succeed, 0 rows written)
PIPELINE_V2_CODE = '''
seen_ids = set()  # TRAP: module-level global, not reset between pipeline runs

def load_silver(rows):
    """Load rows into Silver table — idempotent via seen_ids check."""
    con = duckdb.connect("sigma.duckdb")
    for row in rows:
        if row["transaction_id"] in seen_ids:
            continue                          # skip duplicate
        seen_ids.add(row["transaction_id"])
        con.execute(
            "INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["transaction_date"]]
        )

def main():
    bronze = fetch_bronze()
    silver = transform(bronze)
    load_silver(silver)
'''

# ── Stack trace for Team 6 (Incident Commander) ───────────────────────────────
PROD_STACK_TRACE = """
Traceback (most recent call last):
  File "pipeline.py", line 134, in load_silver
    con.execute(
        "INSERT INTO silver_transactions VALUES (?, ?, ?, ?, ?)",
        [row["transaction_id"], row["amount"], row["status"],
         row["merchant_id"], row["transaction_date"]]
    )
duckdb.duckdb.ConstraintException: Constraint Error:
  Duplicate key "TXN012" violates primary key constraint on silver_transactions
  File "pipeline.py", line 89, in main
    load_silver(silver_rows)
  File "pipeline.py", line 156, in run_pipeline
    main()
RuntimeError: Pipeline failed at Silver load stage after processing 11 records
Timestamp: 2024-01-22 02:47:33 UTC
Environment: prod | Region: us-east-1 | Run ID: run_20240122_0247
"""
