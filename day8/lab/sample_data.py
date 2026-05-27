"""
Day 8 — Sample Data & DuckDB Schema (Complete — no TODOs here)
Reuses Day 7 Sigma DataTech transactions + adds intentionally dirty data
for data quality testing (Soda sprint).

Students run 0_setup_duckdb.py first — it calls this module to populate a local DuckDB.
"""

# ══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS — same as Day 7 + extras with quality issues for Sprint 2
# ══════════════════════════════════════════════════════════════════════════════

TRANSACTIONS_CLEAN = [
    {"transaction_id": "TXN001", "amount": 450.00, "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C001", "transaction_date": "2024-01-15", "payment_method": "UPI"},
    {"transaction_id": "TXN002", "amount": 1200.50, "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C002", "transaction_date": "2024-01-15", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN003", "amount": 89.00, "status": "FAILED", "merchant_id": "M003", "customer_id": "C003", "transaction_date": "2024-01-16", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN004", "amount": 3200.00, "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C001", "transaction_date": "2024-01-16", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN005", "amount": 250.00, "status": "PENDING", "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN006", "amount": 175.50, "status": "COMPLETED", "merchant_id": "M005", "customer_id": "C002", "transaction_date": "2024-01-17", "payment_method": "UPI"},
    {"transaction_id": "TXN007", "amount": 540.00, "status": "FAILED", "merchant_id": "M006", "customer_id": "C005", "transaction_date": "2024-01-18", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN008", "amount": 890.00, "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C003", "transaction_date": "2024-01-18", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN009", "amount": 65.00, "status": "COMPLETED", "merchant_id": "M007", "customer_id": "C006", "transaction_date": "2024-01-19", "payment_method": "UPI"},
    {"transaction_id": "TXN010", "amount": 1450.00, "status": "COMPLETED", "merchant_id": "M008", "customer_id": "C001", "transaction_date": "2024-01-19", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN012", "amount": 780.00, "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN014", "amount": 990.00, "status": "COMPLETED", "merchant_id": "M006", "customer_id": "C003", "transaction_date": "2024-01-23", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN016", "amount": 3400.00, "status": "COMPLETED", "merchant_id": "M008", "customer_id": "C006", "transaction_date": "2024-01-25", "payment_method": "CREDIT_CARD"},
    {"transaction_id": "TXN018", "amount": 560.00, "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C007", "transaction_date": "2024-01-31", "payment_method": "UPI"},
]

TRANSACTIONS_DIRTY = [
    {"transaction_id": None, "amount": 320.00, "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C004", "transaction_date": "2024-01-20", "payment_method": "UPI"},
    {"transaction_id": "TXN011", "amount": -50.00, "status": "FAILED", "merchant_id": "M003", "customer_id": "C007", "transaction_date": "2024-01-20", "payment_method": "DEBIT_CARD"},
    {"transaction_id": "TXN012", "amount": 780.00, "status": "COMPLETED", "merchant_id": "M004", "customer_id": "C002", "transaction_date": "2024-01-21", "payment_method": "CREDIT_CARD"},  # duplicate
    {"transaction_id": "TXN017", "amount": 145.00, "status": "FAILED", "merchant_id": "MXXX", "customer_id": "C009", "transaction_date": "2024-01-28", "payment_method": "DEBIT_CARD"},  # unmatched merchant
    {"transaction_id": "TXN019", "amount": 0.00, "status": "COMPLETED", "merchant_id": "M002", "customer_id": "C001", "transaction_date": "2024-01-29", "payment_method": "UPI"},  # zero amount
    {"transaction_id": "TXN020", "amount": 99999.99, "status": "COMPLETED", "merchant_id": "M001", "customer_id": "C010", "transaction_date": "2099-12-31", "payment_method": "CREDIT_CARD"},  # future date
    {"transaction_id": "TXN015", "amount": 125.00, "status": "PENDING", "merchant_id": "M007", "customer_id": "C005", "transaction_date": "2024-01-24", "payment_method": "UPI"},
]

MERCHANTS = [
    {"merchant_id": "M001", "merchant_name": "Swiggy", "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M002", "merchant_name": "Amazon", "category": "E-Commerce", "city": "Bengaluru"},
    {"merchant_id": "M003", "merchant_name": "Zomato", "category": "Food Delivery", "city": "Bengaluru"},
    {"merchant_id": "M004", "merchant_name": "Ola", "category": "Travel", "city": "Bengaluru"},
    {"merchant_id": "M005", "merchant_name": "BigBasket", "category": "Grocery", "city": "Bengaluru"},
    {"merchant_id": "M006", "merchant_name": "BookMyShow", "category": "Entertainment", "city": "Mumbai"},
    {"merchant_id": "M007", "merchant_name": "MakeMyTrip", "category": "Travel", "city": "Gurugram"},
    {"merchant_id": "M008", "merchant_name": "Flipkart", "category": "E-Commerce", "city": "Bengaluru"},
]

# ══════════════════════════════════════════════════════════════════════════════
# DuckDB TABLE SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

DUCKDB_SCHEMA = {
    "bronze_transactions": """
        CREATE TABLE IF NOT EXISTS bronze_transactions (
            transaction_id VARCHAR,
            amount DOUBLE,
            status VARCHAR,
            merchant_id VARCHAR,
            customer_id VARCHAR,
            transaction_date DATE,
            payment_method VARCHAR,
            ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_file VARCHAR DEFAULT 'sample_data.py'
        )
    """,
    "silver_transactions": """
        CREATE TABLE IF NOT EXISTS silver_transactions (
            transaction_id VARCHAR NOT NULL,
            amount DOUBLE NOT NULL,
            status VARCHAR NOT NULL,
            merchant_id VARCHAR,
            customer_id VARCHAR,
            transaction_date DATE NOT NULL,
            payment_method VARCHAR,
            merchant_name VARCHAR,
            category VARCHAR,
            city VARCHAR,
            quality_flag VARCHAR DEFAULT 'CLEAN',
            ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "gold_merchant_performance": """
        CREATE TABLE IF NOT EXISTS gold_merchant_performance (
            merchant_id VARCHAR,
            merchant_name VARCHAR,
            category VARCHAR,
            city VARCHAR,
            report_date DATE,
            total_revenue DOUBLE,
            txn_count INTEGER,
            failure_rate_pct DOUBLE
        )
    """,
    "gold_daily_summary": """
        CREATE TABLE IF NOT EXISTS gold_daily_summary (
            report_date DATE,
            total_revenue DOUBLE,
            total_txns INTEGER,
            unique_customers INTEGER,
            unique_merchants INTEGER,
            failure_rate_pct DOUBLE
        )
    """,
    "merchants": """
        CREATE TABLE IF NOT EXISTS merchants (
            merchant_id VARCHAR PRIMARY KEY,
            merchant_name VARCHAR,
            category VARCHAR,
            city VARCHAR
        )
    """,
}

# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE FUNCTIONS — simplified versions of Day 7 generated code
# These are what pytest Sprint 1 tests against
# ══════════════════════════════════════════════════════════════════════════════

def transform_bronze_to_silver(transactions: list, merchants: list) -> list:
    """Apply Silver layer rules: filter nulls, filter negatives, deduplicate, enrich."""
    merchant_map = {m["merchant_id"]: m for m in merchants}

    seen_ids = set()
    silver = []
    for txn in transactions:
        if txn["transaction_id"] is None:
            continue
        if txn["amount"] < 0:
            continue
        if txn["transaction_id"] in seen_ids:
            continue
        seen_ids.add(txn["transaction_id"])

        merchant = merchant_map.get(txn["merchant_id"], {})
        row = {
            **txn,
            "merchant_name": merchant.get("merchant_name"),
            "category": merchant.get("category"),
            "city": merchant.get("city"),
            "quality_flag": "CLEAN" if txn["merchant_id"] in merchant_map else "UNMATCHED",
        }
        silver.append(row)
    return silver


def compute_merchant_performance(silver_rows: list) -> list:
    """Gold layer: aggregate revenue and counts per merchant."""
    from collections import defaultdict
    agg = defaultdict(lambda: {"revenue": 0.0, "total": 0, "failed": 0, "name": "", "category": "", "city": ""})

    for row in silver_rows:
        mid = row["merchant_id"]
        agg[mid]["name"] = row.get("merchant_name") or ""
        agg[mid]["category"] = row.get("category") or ""
        agg[mid]["city"] = row.get("city") or ""
        agg[mid]["total"] += 1
        if row["status"] == "COMPLETED":
            agg[mid]["revenue"] += row["amount"]
        elif row["status"] == "FAILED":
            agg[mid]["failed"] += 1

    results = []
    for mid, data in agg.items():
        failure_rate = (data["failed"] / data["total"] * 100) if data["total"] > 0 else 0.0
        results.append({
            "merchant_id": mid,
            "merchant_name": data["name"],
            "category": data["category"],
            "city": data["city"],
            "total_revenue": data["revenue"],
            "txn_count": data["total"],
            "failure_rate_pct": round(failure_rate, 2),
        })
    return results


def compute_daily_summary(silver_rows: list) -> list:
    """Gold layer: one row per date across all merchants."""
    from collections import defaultdict
    agg = defaultdict(lambda: {"revenue": 0.0, "total": 0, "failed": 0, "customers": set(), "merchants": set()})

    for row in silver_rows:
        d = row["transaction_date"]
        agg[d]["total"] += 1
        agg[d]["customers"].add(row["customer_id"])
        agg[d]["merchants"].add(row["merchant_id"])
        if row["status"] == "COMPLETED":
            agg[d]["revenue"] += row["amount"]
        elif row["status"] == "FAILED":
            agg[d]["failed"] += 1

    results = []
    for date, data in sorted(agg.items()):
        failure_rate = (data["failed"] / data["total"] * 100) if data["total"] > 0 else 0.0
        results.append({
            "report_date": date,
            "total_revenue": data["revenue"],
            "total_txns": data["total"],
            "unique_customers": len(data["customers"]),
            "unique_merchants": len(data["merchants"]),
            "failure_rate_pct": round(failure_rate, 2),
        })
    return results
