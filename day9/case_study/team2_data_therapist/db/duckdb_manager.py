"""
DuckDB Manager — Data Therapist
Manages Bronze and Silver DuckDB tables with traceability.
"""

import duckdb
import pandas as pd
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "therapist.duckdb")


def get_connection(read_only=False):
    """Get a DuckDB connection (creates DB if not exists)."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return duckdb.connect(DB_PATH, read_only=read_only)


def init_bronze(df: pd.DataFrame):
    """Create / replace the bronze_transactions table."""
    con = get_connection()
    con.execute("DROP TABLE IF EXISTS bronze_transactions")
    con.execute("""
        CREATE TABLE bronze_transactions (
            transaction_id        VARCHAR,
            customer_id           VARCHAR,
            merchant_name         VARCHAR,
            transaction_amount    DOUBLE,
            transaction_timestamp VARCHAR,
            transaction_type      VARCHAR,
            source_system         VARCHAR,
            payment_method        VARCHAR,
            region                VARCHAR,
            status                VARCHAR
        )
    """)
    con.register("df_view", df)
    con.execute("INSERT INTO bronze_transactions SELECT * FROM df_view")
    count = con.execute("SELECT COUNT(*) FROM bronze_transactions").fetchone()[0]
    con.close()
    return count


def get_bronze_stats(con=None):
    """Return dict with Bronze layer stats."""
    close_after = False
    if con is None:
        con = get_connection()
        close_after = True

    stats = {}
    stats["total_rows"] = con.execute("SELECT COUNT(*) FROM bronze_transactions").fetchone()[0]
    stats["null_transaction_id"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE transaction_id IS NULL"
    ).fetchone()[0]
    stats["null_customer_id"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE customer_id IS NULL"
    ).fetchone()[0]
    stats["null_merchant"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE merchant_name IS NULL"
    ).fetchone()[0]
    stats["duplicate_ids"] = con.execute("""
        SELECT COUNT(*) FROM (
            SELECT transaction_id, COUNT(*) as cnt
            FROM bronze_transactions
            WHERE transaction_id IS NOT NULL
            GROUP BY transaction_id HAVING cnt > 1
        )
    """).fetchone()[0]
    stats["negative_amounts"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE transaction_amount < 0"
    ).fetchone()[0]
    stats["bad_timestamps"] = con.execute("""
        SELECT COUNT(*) FROM bronze_transactions
        WHERE transaction_timestamp IS NULL
           OR transaction_timestamp = 'not-a-date'
           OR transaction_timestamp LIKE '0000%'
           OR CAST(SPLIT_PART(transaction_timestamp, '-', 1) AS INTEGER) > 2030
           OR CAST(SPLIT_PART(transaction_timestamp, '-', 2) AS INTEGER) > 12
    """).fetchone()[0]
    stats["invalid_types"] = con.execute("""
        SELECT COUNT(*) FROM bronze_transactions
        WHERE transaction_type NOT IN ('PURCHASE','REFUND','CHARGEBACK','TRANSFER')
    """).fetchone()[0]
    stats["outlier_amounts"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE transaction_amount > 100000"
    ).fetchone()[0]
    stats["whitespace_merchants"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE merchant_name != TRIM(merchant_name) AND merchant_name IS NOT NULL"
    ).fetchone()[0]
    stats["invalid_source_systems"] = con.execute(
        "SELECT COUNT(*) FROM bronze_transactions WHERE source_system NOT IN ('SYS_A','SYS_B','SYS_C')"
    ).fetchone()[0]

    if close_after:
        con.close()
    return stats


def create_silver_from_approved_fixes(approved_fixes: list, df_bronze: pd.DataFrame):
    """
    Apply approved fixes to Bronze data and create Silver table.
    Returns (silver_df, sql_log, row_stats)
    """
    con = get_connection()
    con.execute("DROP TABLE IF EXISTS bronze_working")
    con.register("bronze_df", df_bronze)
    con.execute("CREATE TABLE bronze_working AS SELECT * FROM bronze_df")

    sql_log = []
    row_stats = {
        "bronze_original": len(df_bronze),
        "removed_rows": 0,
        "modified_rows": 0,
    }

    # Map fix keys to actual SQL transformations
    fix_sqls = {
        "fix_duplicates": {
            "sql": """
                CREATE OR REPLACE TABLE bronze_working AS
                SELECT * FROM (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY transaction_timestamp DESC) as rn
                    FROM bronze_working
                    WHERE transaction_id IS NOT NULL
                ) WHERE rn = 1
            """,
            "description": "Deduplicate: keep latest record per transaction_id",
        },
        "fix_null_merchant": {
            "sql": "UPDATE bronze_working SET merchant_name = 'UNKNOWN' WHERE merchant_name IS NULL",
            "description": "Fill null merchant names with UNKNOWN",
        },
        "fix_negative_amounts": {
            # THE DANGEROUS FIX! Looks right but flips legitimate refunds too.
            "sql": "UPDATE bronze_working SET transaction_amount = ABS(transaction_amount) WHERE transaction_amount < 0",
            "description": "Convert all negative amounts to positive (ABS)",
        },
        "fix_bad_timestamps": {
            "sql": """
                CREATE OR REPLACE TABLE bronze_working AS
                SELECT * FROM bronze_working
                WHERE transaction_timestamp NOT IN ('not-a-date', '0000-00-00 00:00:00', '2024-13-45 00:00:00')
                  AND (CAST(SPLIT_PART(transaction_timestamp, '-', 1) AS INTEGER) <= 2030)
            """,
            "description": "Remove rows with malformed or impossible timestamps",
        },
        "fix_null_customer_id": {
            "sql": "UPDATE bronze_working SET customer_id = 'UNKNOWN_CUST' WHERE customer_id IS NULL",
            "description": "Fill null customer IDs with UNKNOWN_CUST",
        },
        "fix_invalid_types": {
            "sql": "UPDATE bronze_working SET transaction_type = 'UNKNOWN' WHERE transaction_type NOT IN ('PURCHASE','REFUND','CHARGEBACK','TRANSFER')",
            "description": "Recode invalid transaction types to UNKNOWN",
        },
        "fix_outliers": {
            "sql": """
                CREATE OR REPLACE TABLE bronze_working AS
                SELECT * FROM bronze_working WHERE transaction_amount <= 100000
            """,
            "description": "Remove outlier transactions above ₹100,000",
        },
        "fix_whitespace": {
            "sql": "UPDATE bronze_working SET merchant_name = TRIM(merchant_name) WHERE merchant_name IS NOT NULL",
            "description": "Trim leading/trailing whitespace from merchant names",
        },
        "fix_invalid_source": {
            "sql": """
                CREATE OR REPLACE TABLE bronze_working AS
                SELECT * FROM bronze_working WHERE source_system IN ('SYS_A','SYS_B','SYS_C')
            """,
            "description": "Remove rows with invalid source system codes",
        },
        "fix_null_txn_id": {
            "sql": """
                CREATE OR REPLACE TABLE bronze_working AS
                SELECT * FROM bronze_working WHERE transaction_id IS NOT NULL
            """,
            "description": "Remove rows with null transaction IDs",
        },
    }

    for fix_key in approved_fixes:
        if fix_key in fix_sqls:
            fix_info = fix_sqls[fix_key]
            try:
                con.execute(fix_info["sql"])
                sql_log.append({
                    "fix": fix_key,
                    "sql": fix_info["sql"].strip(),
                    "description": fix_info["description"],
                    "status": "✅ Applied",
                })
            except Exception as e:
                sql_log.append({
                    "fix": fix_key,
                    "sql": fix_info["sql"].strip(),
                    "description": fix_info["description"],
                    "status": f"❌ Error: {e}",
                })

    # Materialize Silver
    silver_df = con.execute("SELECT * FROM bronze_working").df()
    row_stats["silver_rows"] = len(silver_df)
    row_stats["removed_rows"] = row_stats["bronze_original"] - len(silver_df)

    # Write Silver table
    con.execute("DROP TABLE IF EXISTS silver_transactions")
    con.register("silver_df_view", silver_df)
    con.execute("CREATE TABLE silver_transactions AS SELECT * FROM silver_df_view")

    con.close()
    return silver_df, sql_log, row_stats


def get_silver_stats(silver_df: pd.DataFrame):
    """Compute downstream analytics on Silver data."""
    stats = {}

    if silver_df.empty:
        return {"error": "Silver table is empty"}

    # Total revenue (COMPLETED only)
    completed = silver_df[silver_df["status"] == "COMPLETED"]
    stats["total_revenue"] = completed["transaction_amount"].sum()
    stats["total_transactions"] = len(silver_df)
    stats["completed_count"] = len(completed)

    # Refund analysis — THE TRAP reveals itself here
    refunds = silver_df[silver_df["transaction_type"] == "REFUND"]
    stats["refund_count"] = len(refunds)
    stats["refund_revenue"] = refunds["transaction_amount"].sum()
    stats["negative_amounts_remaining"] = (silver_df["transaction_amount"] < 0).sum()

    # Merchant-level revenue
    merch_rev = (
        completed.groupby("merchant_name")["transaction_amount"].sum()
        .sort_values(ascending=False)
        .head(10)
        .to_dict()
    )
    stats["merchant_revenue"] = merch_rev

    # Payment method distribution
    stats["payment_method_dist"] = silver_df["payment_method"].value_counts().to_dict()

    # Status distribution
    stats["status_dist"] = silver_df["status"].value_counts().to_dict()

    # Null checks remaining
    stats["null_merchant_remaining"] = silver_df["merchant_name"].isnull().sum()
    stats["null_customer_remaining"] = silver_df["customer_id"].isnull().sum()

    return stats


def get_bronze_df():
    """Load Bronze transactions as DataFrame."""
    con = get_connection()
    try:
        df = con.execute("SELECT * FROM bronze_transactions").df()
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df


def get_silver_df():
    """Load Silver transactions as DataFrame."""
    con = get_connection()
    try:
        df = con.execute("SELECT * FROM silver_transactions").df()
    except Exception:
        df = pd.DataFrame()
    con.close()
    return df
