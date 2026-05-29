"""
Downstream Validation Module for Data Therapist.
Computes and compares financial and operational metrics across Bronze, Naive Silver, and Correct Silver layers.
This forms the core downstream observability engine, revealing the impact of the AI trap.
"""

import pandas as pd
import duckdb

def calculate_downstream_metrics(db_manager, table_name):
    """
    Calculates key financial and operational metrics for a given table in DuckDB.
    Returns a dictionary of business dashboard metrics.
    """
    conn = db_manager.get_connection()
    try:
        # Check if the table exists
        exists = conn.execute(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'").fetchone()[0]
        if not exists:
            return {}

        total_rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        if total_rows == 0:
            return {
                "total_rows": 0,
                "gross_revenue": 0.0,
                "refunds_count": 0,
                "refunds_amount": 0.0,
                "net_revenue": 0.0,
                "purchase_count": 0,
                "chargeback_count": 0,
                "merchant_distribution": [],
                "payment_distribution": []
            }

        # 1. Financial Metrics
        # Gross Revenue: Sum of PURCHASES (or all positive transactions)
        gross_rev = conn.execute(f"""
            SELECT COALESCE(SUM(transaction_amount), 0.0) 
            FROM {table_name} 
            WHERE transaction_amount > 0 AND (transaction_type = 'PURCHASE' OR transaction_type IS NULL OR transaction_type = 'SUCCESS')
        """).fetchone()[0]

        # Refund Metrics
        refunds_count = conn.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE transaction_amount < 0 OR transaction_type = 'REFUND'
        """).fetchone()[0]

        refunds_amount = conn.execute(f"""
            SELECT COALESCE(SUM(transaction_amount), 0.0) 
            FROM {table_name} 
            WHERE transaction_amount < 0 OR transaction_type = 'REFUND'
        """).fetchone()[0]

        # Chargebacks
        chargeback_count = conn.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE transaction_type = 'CHARGEBACK'
        """).fetchone()[0]

        purchase_count = conn.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE transaction_type = 'PURCHASE' OR transaction_type = 'SUCCESS' OR transaction_type IS NULL
        """).fetchone()[0]

        # Net Revenue: Gross Revenue + Refunds Amount (which is negative)
        # Note: If refunds are positive (due to naive ABS fix), net revenue will be gross_revenue + absolute refunds,
        # which represents the inflated revenue error!
        net_rev = conn.execute(f"SELECT COALESCE(SUM(transaction_amount), 0.0) FROM {table_name}").fetchone()[0]

        # 2. Merchant Performance (Rankings)
        merchant_ranking_query = f"""
            SELECT COALESCE(merchant_name, 'NULL') as merchant,
                   ROUND(SUM(transaction_amount), 2) as revenue,
                   COUNT(*) as txn_count
            FROM {table_name}
            GROUP BY merchant_name
            ORDER BY revenue DESC
            LIMIT 5
        """
        merchants_df = conn.execute(merchant_ranking_query).fetchdf()
        merchant_distribution = merchants_df.to_dict(orient='records')

        # 3. Payment Method Distribution
        payment_query = f"""
            SELECT COALESCE(payment_method, 'UNKNOWN') as method,
                   COUNT(*) as txn_count
            FROM {table_name}
            GROUP BY payment_method
            ORDER BY txn_count DESC
        """
        payment_df = conn.execute(payment_query).fetchdf()
        payment_distribution = payment_df.to_dict(orient='records')

        # 4. Outliers and Fraud signals
        high_value_alerts = conn.execute(f"""
            SELECT COUNT(*) 
            FROM {table_name} 
            WHERE ABS(transaction_amount) > 100000
        """).fetchone()[0]

        return {
            "total_rows": total_rows,
            "gross_revenue": round(gross_rev, 2),
            "refunds_count": refunds_count,
            "refunds_amount": round(refunds_amount, 2),
            "chargeback_count": chargeback_count,
            "purchase_count": purchase_count,
            "net_revenue": round(net_rev, 2),
            "merchant_distribution": merchant_distribution,
            "payment_distribution": payment_distribution,
            "high_value_alerts": high_value_alerts
        }

    except Exception as e:
        print(f"Error calculating downstream metrics: {e}")
        return {}
    finally:
        conn.close()

def generate_comparison_report(db_manager):
    """
    Simulates and generates downstream validation comparison metrics for:
    1. Bronze Raw
    2. Naive Silver (with absolute values)
    3. Correct Silver (with safe negatives)
    """
    # Grab active decisions
    decisions = db_manager.get_decisions()
    
    # Run the dynamic pipeline with Naive ABS fix
    db_manager.execute_remediation_pipeline(decisions, use_naive_refund_fix=True)
    naive_metrics = calculate_downstream_metrics(db_manager, "silver_transactions")
    
    # Run the dynamic pipeline with Safe Human fix
    db_manager.execute_remediation_pipeline(decisions, use_naive_refund_fix=False)
    correct_metrics = calculate_downstream_metrics(db_manager, "silver_transactions")
    
    # Calculate raw Bronze metrics
    bronze_metrics = calculate_downstream_metrics(db_manager, "bronze_transactions")

    # Restore the active pipeline to match the user's current decision setting
    # We default to showing the naive/correct state depending on the dashboard toggle.
    return {
        "bronze": bronze_metrics,
        "naive_silver": naive_metrics,
        "correct_silver": correct_metrics
    }
