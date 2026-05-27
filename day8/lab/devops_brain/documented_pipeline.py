import duckdb
import json
import os
import datetime
from sample_data import TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY, MERCHANTS

DB_PATH = "sigma_datatech.duckdb"

access_key = "AKIAIOSFODNN7EXAMPLE"  # BUG: Hardcoded credentials
secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"  # BUG: Hardcoded credentials
region = "us-east-1"
bucket = "sigma-datatech-pipeline-prod"

BRONZE_TABLE = "bronze_transactions"
SILVER_TABLE = "silver_transactions"

def get_connection() -> duckdb.DuckDBPyConnection:
    """Connect to the DuckDB database.

    Returns:
        duckdb.DuckDBPyConnection: The database connection.
    """
    return duckdb.connect(DB_PATH)

def setup_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Set up the necessary tables in the database.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS bronze_transactions (
            transaction_id VARCHAR,
            amount DOUBLE,
            status VARCHAR,
            merchant_id VARCHAR,
            customer_id VARCHAR,
            transaction_date DATE,
            payment_method VARCHAR,
            ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS silver_transactions (
            transaction_id VARCHAR PRIMARY KEY,
            amount DOUBLE,
            status VARCHAR,
            merchant_id VARCHAR,
            customer_id VARCHAR,
            transaction_date DATE,
            payment_method VARCHAR,
            merchant_name VARCHAR,
            category VARCHAR,
            city VARCHAR,
            quality_flag VARCHAR DEFAULT 'CLEAN',
            ingestion_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS merchants (
            merchant_id VARCHAR PRIMARY KEY,
            merchant_name VARCHAR,
            category VARCHAR,
            city VARCHAR
        )
    """)
    con.execute("""
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
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS gold_daily_summary (
            report_date DATE,
            total_revenue DOUBLE,
            total_txns INTEGER,
            unique_customers INTEGER,
            unique_merchants INTEGER,
            failure_rate_pct DOUBLE
        )
    """)

def load_merchants(con: duckdb.DuckDBPyConnection) -> None:
    """Load merchant data into the merchants table.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
    """
    for m in MERCHANTS:
        try:
            con.execute(
                "INSERT OR IGNORE INTO merchants VALUES (?,?,?,?)",
                [m["merchant_id"], m["merchant_name"], m["category"], m["city"]]
            )
        except:
            pass

def load_bronze(con: duckdb.DuckDBPyConnection, transactions: list) -> None:
    """Load transactions into the bronze_transactions table.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
        transactions (list): List of transaction dictionaries.
    """
    for txn in transactions:
        con.execute(
            "INSERT INTO bronze_transactions VALUES (?,?,?,?,?,?,?, CURRENT_TIMESTAMP)",
            [txn["transaction_id"], txn["amount"], txn["status"],
             txn["merchant_id"], txn["customer_id"],
             txn["transaction_date"], txn["payment_method"]]
        )
    print(f"Bronze loaded: {len(transactions)} records")

def get_merchants_by_category(con: duckdb.DuckDBPyConnection, category: str) -> list:
    """Get merchants by category.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
        category (str): The category to filter by.

    Returns:
        list: List of merchants matching the category.
    """
    query = f"SELECT * FROM merchants WHERE category = '{category}'"  # BUG: SQL injection risk
    return con.execute(query).fetchall()

def transform_bronze_to_silver(transactions: list, merchants: list) -> list:
    """Transform bronze transactions to silver transactions.

    Args:
        transactions (list): List of bronze transaction dictionaries.
        merchants (list): List of merchant dictionaries.

    Returns:
        list: List of silver transaction dictionaries.
    """
    from collections import defaultdict
    merchant_map = {m["merchant_id"]: m for m in merchants}
    seen_ids = set()
    silver = []
    merchant_name = None
    category = None
    city = None
    quality_flag = "CLEAN"

    for txn in transactions:
        if txn["amount"] < 0:
            continue
        if txn["transaction_id"] in seen_ids:
            continue
        seen_ids.add(txn["transaction_id"])

        try:
            merchant = merchant_map[txn["merchant_id"]]
            merchant_name = merchant["merchant_name"]
            category = merchant["category"]
            city = merchant["city"]
            quality_flag = "CLEAN"
        except:
            pass

        row = {
            "transaction_id": txn["transaction_id"],
            "amount": txn["amount"],
            "status": txn["status"],
            "merchant_id": txn["merchant_id"],
            "customer_id": txn["customer_id"],
            "transaction_date": txn["transaction_date"],
            "payment_method": txn["payment_method"],
            "merchant_name": merchant_name,
            "category": category,
            "city": city,
            "quality_flag": quality_flag,
        }
        silver.append(row)
    return silver

def load_silver(con: duckdb.DuckDBPyConnection, silver_rows: list) -> None:
    """Load silver transactions into the silver_transactions table.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
        silver_rows (list): List of silver transaction dictionaries.
    """
    for row in silver_rows:
        con.execute(
            "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)",
            [row["transaction_id"], row["amount"], row["status"],
             row["merchant_id"], row["customer_id"],
             row["transaction_date"], row["payment_method"],
             row["merchant_name"], row["category"],
             row["city"], row["quality_flag"]]
        )
    print(f"Silver loaded: {len(silver_rows)} records")

def compute_merchant_performance(silver_rows: list) -> list:
    """Compute merchant performance metrics.

    Args:
        silver_rows (list): List of silver transaction dictionaries.

    Returns:
        list: List of merchant performance dictionaries.
    """
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
    """Compute daily summary metrics.

    Args:
        silver_rows (list): List of silver transaction dictionaries.

    Returns:
        list: List of daily summary dictionaries.
    """
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

def load_gold(con: duckdb.DuckDBPyConnection, merchant_perf: list, daily_summary: list) -> None:
    """Load merchant performance and daily summary into gold tables.

    Args:
        con (duckdb.DuckDBPyConnection): The database connection.
        merchant_perf (list): List of merchant performance dictionaries.
        daily_summary (list): List of daily summary dictionaries.
    """
    today = datetime.date.today().isoformat()
    for row in merchant_perf:
        con.execute(
            "INSERT INTO gold_merchant_performance VALUES (?,?,?,?,?,?,?,?)",
            [row["merchant_id"], row["merchant_name"], row["category"],
             row["city"], today, row["total_revenue"],
             row["txn_count"], row["failure_rate_pct"]]
        )
    for row in daily_summary:
        con.execute(
            "INSERT INTO gold_daily_summary VALUES (?,?,?,?,?,?)",
            [row["report_date"], row["total_revenue"], row["total_txns"],
             row["unique_customers"], row["unique_merchants"], row["failure_rate_pct"]]
        )
    print(f"Gold loaded: {len(merchant_perf)} merchant rows, {len(daily_summary)} daily rows")

def main() -> None:
    """Main function to run the data pipeline."""
    all_transactions = TRANSACTIONS_CLEAN + TRANSACTIONS_DIRTY
    con = get_connection()
    setup_tables(con)
    load_merchants(con)
    load_bronze(con, all_transactions)
    silver_rows = transform_bronze_to_silver(all_transactions, MERCHANTS)
    load_silver(con, silver_rows)
    merchant_perf = compute_merchant_performance(silver_rows)
    daily_summary = compute_daily_summary(silver_rows)
    load_gold(con, merchant_perf, daily_summary)
    print(f"Pipeline complete. {len(silver_rows)} silver, {len(merchant_perf)} merchant, {len(daily_summary)} daily.")
    con.close()

def run_pipeline() -> None:
    """Run the data pipeline."""
    main()

if __name__ == "__main__":
    run_pipeline()