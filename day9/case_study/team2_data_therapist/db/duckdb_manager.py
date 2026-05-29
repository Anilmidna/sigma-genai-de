"""
DuckDB Database Manager for Data Therapist.
Manages the connection, tables, dynamic SQL remediation execution, and audit logging.
"""

import os
import duckdb
import pandas as pd
from datetime import datetime

class DuckDBManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # Default to the workspace data folder
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.db_dir = os.path.join(self.base_dir, "data")
            os.makedirs(self.db_dir, exist_ok=True)
            self.db_path = os.path.join(self.db_dir, "sigma_platform.duckdb")
        else:
            self.db_path = db_path
            self.db_dir = os.path.dirname(db_path)
            if self.db_dir:
                os.makedirs(self.db_dir, exist_ok=True)

    def get_connection(self):
        """Returns a connection to the DuckDB database."""
        return duckdb.connect(self.db_path)

    def init_database(self, df_bronze):
        """
        Initializes the database:
        1. Creates bronze_transactions and populates it with the dirty dataset.
        2. Creates an empty silver_transactions table.
        3. Creates the treatment_decisions table for human-in-the-loop persistence.
        """
        conn = self.get_connection()
        try:
            # 1. Bronze Layer
            conn.execute("DROP TABLE IF EXISTS bronze_transactions")
            # We can register the pandas dataframe and create the table
            conn.register("df_temp", df_bronze)
            conn.execute("CREATE TABLE bronze_transactions AS SELECT * FROM df_temp")
            conn.unregister("df_temp")
            
            # 2. Silver Layer
            conn.execute("DROP TABLE IF EXISTS silver_transactions")
            conn.execute("""
                CREATE TABLE silver_transactions (
                    transaction_id   VARCHAR,
                    customer_id      VARCHAR,
                    merchant_name    VARCHAR,
                    transaction_amount DOUBLE,
                    transaction_timestamp VARCHAR,
                    transaction_type VARCHAR,
                    source_system   VARCHAR,
                    payment_method   VARCHAR,
                    region           VARCHAR,
                    quality_flag     VARCHAR DEFAULT 'CLEAN'
                )
            """)
            
            # Initialize Silver with all Bronze data initially (we'll clean it in Round 3)
            conn.execute("INSERT INTO silver_transactions SELECT *, 'RAW' FROM bronze_transactions")
            
            # 3. Treatment Decisions persistency
            conn.execute("""
                CREATE TABLE IF NOT EXISTS treatment_decisions (
                    issue_id VARCHAR PRIMARY KEY,
                    issue_title VARCHAR,
                    decision VARCHAR, -- 'APPLY', 'REJECT', 'INVESTIGATE'
                    updated_at TIMESTAMP,
                    applied_sql VARCHAR
                )
            """)
            
            # 4. Ingest raw merchants for enrichment validation if needed
            conn.execute("DROP TABLE IF EXISTS merchants")
            conn.execute("""
                CREATE TABLE merchants (
                    merchant_id VARCHAR PRIMARY KEY,
                    merchant_name VARCHAR,
                    category VARCHAR,
                    city VARCHAR
                )
            """)
            merchants_data = [
                ("M001", "Swiggy", "Food Delivery", "Bengaluru"),
                ("M002", "Amazon", "E-Commerce", "Bengaluru"),
                ("M003", "Zomato", "Food Delivery", "Bengaluru"),
                ("M004", "Uber", "Travel", "Bengaluru"),
                ("M005", "BigBasket", "Grocery", "Bengaluru"),
                ("M006", "Netflix", "Entertainment", "Mumbai"),
                ("M007", "Flipkart", "E-Commerce", "Bengaluru"),
            ]
            for m in merchants_data:
                conn.execute("INSERT INTO merchants VALUES (?,?,?,?)", m)
                
        finally:
            conn.close()

    def get_table_as_df(self, table_name):
        """Reads a table and returns a Pandas DataFrame."""
        conn = self.get_connection()
        try:
            df = conn.execute(f"SELECT * FROM {table_name}").fetchdf()
            return df
        finally:
            conn.close()

    def get_row_count(self, table_name):
        """Returns the number of rows in a table."""
        conn = self.get_connection()
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            return count
        finally:
            conn.close()

    def get_anomaly_metrics(self, table_name):
        """Returns key data quality anomaly counts for comparison."""
        conn = self.get_connection()
        try:
            # Duplicate transaction IDs
            dup_ids = conn.execute(f"""
                SELECT COUNT(*) - COUNT(DISTINCT transaction_id) 
                FROM {table_name} 
                WHERE transaction_id IS NOT NULL
            """).fetchone()[0]
            
            # Null/missing values
            null_merchants = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE merchant_name IS NULL").fetchone()[0]
            null_customers = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE customer_id IS NULL").fetchone()[0]
            null_ids = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE transaction_id IS NULL").fetchone()[0]
            
            # Negative amounts
            neg_amounts = conn.execute(f"SELECT COUNT(*) FROM {table_name} WHERE transaction_amount < 0").fetchone()[0]
            
            # Malformed/Impossible timestamps
            bad_timestamps = conn.execute(f"""
                SELECT COUNT(*) FROM {table_name} 
                WHERE transaction_timestamp >= '2099-01-01' 
                   OR transaction_timestamp LIKE '%/%' 
                   OR transaction_timestamp LIKE '%-%' AND length(transaction_timestamp) = 10
            """).fetchone()[0]
            
            # Inconsistent Merchant Names (containing lowercase, variations, etc.)
            inconsistent_merchants = conn.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE merchant_name IS NOT NULL AND (
                    merchant_name LIKE '%Inc%' OR 
                    merchant_name LIKE '%Ltd%' OR 
                    merchant_name LIKE '%Subscription%' OR
                    merchant_name LIKE '%Rides%' OR
                    merchant_name LIKE '%Delivery%' OR
                    merchant_name = LOWER(merchant_name) OR
                    merchant_name = UPPER(merchant_name) OR
                    merchant_name LIKE ' %' OR
                    merchant_name LIKE '% '
                )
            """).fetchone()[0]

            return {
                "total_rows": self.get_row_count(table_name),
                "duplicate_ids": max(0, dup_ids),
                "null_merchants": null_merchants,
                "null_customers": null_customers,
                "null_ids": null_ids,
                "negative_amounts": neg_amounts,
                "bad_timestamps": bad_timestamps,
                "inconsistent_merchants": inconsistent_merchants,
                "total_anomalies": max(0, dup_ids) + null_merchants + null_customers + null_ids + bad_timestamps + inconsistent_merchants
            }
        except Exception as e:
            print(f"Error reading anomaly metrics: {e}")
            return {}
        finally:
            conn.close()

    def save_decision(self, issue_id, issue_title, decision, applied_sql=""):
        """Saves a remediation decision to the audit log."""
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT OR REPLACE INTO treatment_decisions (issue_id, issue_title, decision, updated_at, applied_sql)
                VALUES (?, ?, ?, ?, ?)
            """, (issue_id, issue_title, decision, datetime.now(), applied_sql))
        finally:
            conn.close()

    def get_decisions(self):
        """Returns all treatment decisions as a dict."""
        conn = self.get_connection()
        try:
            rows = conn.execute("SELECT issue_id, decision, applied_sql FROM treatment_decisions").fetchall()
            return {r[0]: {"decision": r[1], "applied_sql": r[2]} for r in rows}
        except Exception:
            return {}
        finally:
            conn.close()

    def clear_decisions(self):
        """Resets all decisions."""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM treatment_decisions")
        finally:
            conn.close()

    def execute_remediation_pipeline(self, decisions, use_naive_refund_fix=True):
        """
        Executes the Silver load pipeline from Bronze, applying only approved fixes.
        We can run this dynamically whenever the user updates the treatment plan!
        
        Args:
            decisions (dict): A dictionary of issue_id -> 'APPLY' or 'REJECT' or 'INVESTIGATE'
            use_naive_refund_fix (bool): If True, applies the dangerous AI fix to convert negative numbers to positive.
                                         If False, applies the safe fix (preserving negatives, flagging them).
        """
        conn = self.get_connection()
        try:
            # 1. Reset Silver to raw Bronze rows
            conn.execute("DELETE FROM silver_transactions")
            conn.execute("INSERT INTO silver_transactions SELECT *, 'RAW' FROM bronze_transactions")
            
            executed_sqls = []

            # 2. Apply "Null Transaction IDs" Fix
            # If approved, we delete rows where transaction_id is NULL
            if decisions.get("null_ids", {}).get("decision") == "APPLY":
                sql = "DELETE FROM silver_transactions WHERE transaction_id IS NULL;"
                conn.execute(sql)
                executed_sqls.append(("null_ids", sql))
            elif decisions.get("null_ids", {}).get("decision") == "REJECT":
                # Do nothing, bad data remains
                pass

            # 3. Apply "Duplicate Transaction IDs" Fix
            # If approved, deduplicate keeping the latest timestamp
            if decisions.get("duplicates", {}).get("decision") == "APPLY":
                sql = """
                WITH ranked AS (
                    SELECT transaction_id, transaction_timestamp,
                           row_number() OVER (PARTITION BY transaction_id ORDER BY transaction_timestamp DESC) as rn
                    FROM silver_transactions
                    WHERE transaction_id IS NOT NULL
                )
                DELETE FROM silver_transactions
                WHERE (transaction_id, transaction_timestamp) IN (
                    SELECT transaction_id, transaction_timestamp FROM ranked WHERE rn > 1
                );
                """
                conn.execute(sql)
                executed_sqls.append(("duplicates", sql))

            # 4. Apply "Null Merchant Names" Fix
            if decisions.get("null_merchants", {}).get("decision") == "APPLY":
                sql = "UPDATE silver_transactions SET merchant_name = 'UNKNOWN' WHERE merchant_name IS NULL;"
                conn.execute(sql)
                executed_sqls.append(("null_merchants", sql))

            # 5. Apply "Missing Customer IDs" Fix
            if decisions.get("null_customers", {}).get("decision") == "APPLY":
                sql = "UPDATE silver_transactions SET customer_id = 'GUEST' WHERE customer_id IS NULL;"
                conn.execute(sql)
                executed_sqls.append(("null_customers", sql))

            # 6. Apply "Malformed Timestamps" Fix
            if decisions.get("malformed_timestamps", {}).get("decision") == "APPLY":
                sql = """
                UPDATE silver_transactions
                SET transaction_timestamp = CASE
                    WHEN transaction_timestamp LIKE '%/%' THEN strftime(strptime(transaction_timestamp, '%Y/%m/%d %H:%M'), '%Y-%m-%d %H:%M:%S')
                    WHEN transaction_timestamp LIKE '%-%' AND length(transaction_timestamp) = 10 THEN strftime(strptime(transaction_timestamp, '%d-%m-%Y'), '%Y-%m-%d %H:%M:%S')
                    ELSE transaction_timestamp
                END
                WHERE transaction_timestamp NOT LIKE '2099%';
                """
                conn.execute(sql)
                executed_sqls.append(("malformed_timestamps", sql))

            # 7. Apply "Impossible/Future Timestamps" Fix
            if decisions.get("future_timestamps", {}).get("decision") == "APPLY":
                sql = "DELETE FROM silver_transactions WHERE transaction_timestamp >= '2099-01-01';"
                conn.execute(sql)
                executed_sqls.append(("future_timestamps", sql))

            # 8. Apply "Inconsistent Merchant Spellings" Fix
            if decisions.get("merchant_spellings", {}).get("decision") == "APPLY":
                sql = """
                UPDATE silver_transactions
                SET merchant_name = CASE
                    WHEN upper(trim(merchant_name)) LIKE 'AMAZON%' THEN 'Amazon'
                    WHEN upper(trim(merchant_name)) LIKE 'SWIGGY%' THEN 'Swiggy'
                    WHEN upper(trim(merchant_name)) LIKE 'ZOMATO%' THEN 'Zomato'
                    WHEN upper(trim(merchant_name)) LIKE 'FLIPKART%' THEN 'Flipkart'
                    WHEN upper(trim(merchant_name)) LIKE 'NETFLIX%' THEN 'Netflix'
                    WHEN upper(trim(merchant_name)) LIKE 'UBER%' THEN 'Uber'
                    ELSE trim(merchant_name)
                END
                WHERE merchant_name IS NOT NULL;
                """
                conn.execute(sql)
                executed_sqls.append(("merchant_spellings", sql))

            # 9. Apply "Negative Amounts" (THE TRAP)
            if decisions.get("negative_amounts", {}).get("decision") == "APPLY":
                if use_naive_refund_fix:
                    # Dangerous Fix (Convert all negatives to positive)
                    sql = """
                    UPDATE silver_transactions
                    SET transaction_amount = abs(transaction_amount)
                    WHERE transaction_amount < 0;
                    """
                    conn.execute(sql)
                    executed_sqls.append(("negative_amounts", f"-- [DANGEROUS AI RECOMMENDATION APPROVED]\n{sql}"))
                else:
                    # Correct Fix (Keep negative, validate that it is classified as REFUND or CHARGEBACK, else fix type)
                    sql = """
                    UPDATE silver_transactions
                    SET transaction_type = CASE 
                        WHEN transaction_type NOT IN ('REFUND', 'CHARGEBACK') THEN 'REFUND' 
                        ELSE transaction_type 
                    END
                    WHERE transaction_amount < 0;
                    """
                    conn.execute(sql)
                    executed_sqls.append(("negative_amounts", f"-- [SAFE HUMAN Remediator Approved]\n{sql}"))

            # Update quality flags in Silver for processed rows
            conn.execute("UPDATE silver_transactions SET quality_flag = 'CLEANED' WHERE quality_flag = 'RAW'")

            return executed_sqls
            
        finally:
            conn.close()
