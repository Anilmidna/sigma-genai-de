"""
Verification Script for Data Therapist.
Tests synthetic generation, db schemas, LLM report mappings, and dynamic sql cleansers.
"""

import sys
import os

# Adjust paths to make sure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("==================================================")
print("Data Therapist Simulator — Backend Pipeline Test")
print("==================================================")

try:
    # 1. Test data generator
    print("\n[1/5] Testing Synthetic Data Generator...")
    from utils.synthetic_data_generator import generate_dirty_data
    df = generate_dirty_data(200)
    print(f"  SUCCESS: Generated {len(df)} rows.")
    print(f"  Columns: {df.columns.tolist()}")

    # 2. Test DB connection & table initialization
    print("\n[2/5] Testing DuckDB Manager Schema Init...")
    from db.duckdb_manager import DuckDBManager
    db_mgr = DuckDBManager()
    db_mgr.init_database(df)
    print(f"  SUCCESS: Database initialized at: {db_mgr.db_path}")
    print(f"  Bronze table count: {db_mgr.get_row_count('bronze_transactions')} rows.")
    print(f"  Silver table count: {db_mgr.get_row_count('silver_transactions')} rows.")

    # 3. Test Diagnosis Engine
    print("\n[3/5] Testing AI Diagnosis Engine...")
    from llm.diagnosis_engine import diagnose_dataset
    diagnoses = diagnose_dataset(df, use_bedrock=False)
    print(f"  SUCCESS: Detected {len(diagnoses)} issues in mock report.")
    print(f"  First issue: {diagnoses[0]['title']} (Severity: {diagnoses[0]['severity']})")

    # 4. Test Remediation Pipeline Executions
    print("\n[4/5] Testing Dynamic Remediation SQL Execution...")
    # Pre-seed decisions dict
    decisions = {
        "duplicates": {"decision": "APPLY"},
        "null_ids": {"decision": "APPLY"},
        "null_merchants": {"decision": "APPLY"},
        "null_customers": {"decision": "APPLY"},
        "malformed_timestamps": {"decision": "APPLY"},
        "future_timestamps": {"decision": "APPLY"},
        "merchant_spellings": {"decision": "APPLY"},
        "negative_amounts": {"decision": "APPLY"}, # Naive absolute value fix
        "outliers": {"decision": "APPLY"}
    }
    
    # Run Naive pipeline
    sqls_naive = db_mgr.execute_remediation_pipeline(decisions, use_naive_refund_fix=True)
    naive_count = db_mgr.get_row_count("silver_transactions")
    print(f"  SUCCESS: Executed Naive SQL pipeline. Applied {len(sqls_naive)} fixes.")
    print(f"  Silver table rows remaining: {naive_count} rows.")

    # Run Correct pipeline
    sqls_correct = db_mgr.execute_remediation_pipeline(decisions, use_naive_refund_fix=False)
    correct_count = db_mgr.get_row_count("silver_transactions")
    print(f"  SUCCESS: Executed Correct SQL pipeline. Applied {len(sqls_correct)} fixes.")
    print(f"  Silver table rows remaining: {correct_count} rows.")

    # 5. Test Downstream Validators
    print("\n[5/5] Testing Downstream Business Metric Validators...")
    from utils.validators import generate_comparison_report
    # We first save decision status to DB to match the pipeline report
    for k, v in decisions.items():
        db_mgr.save_decision(k, k.replace("_", " ").title(), v["decision"])
        
    report = generate_comparison_report(db_mgr)
    print("  SUCCESS: Generated Downstream Comparison Report.")
    print(f"  Bronze Net Revenue:  ${report['bronze']['net_revenue']:,}")
    print(f"  Naive Silver Revenue: ${report['naive_silver']['net_revenue']:,}  (Refunds count: {report['naive_silver']['refunds_count']})")
    print(f"  Correct Silver Rev:  ${report['correct_silver']['net_revenue']:,}  (Refunds count: {report['correct_silver']['refunds_count']})")

    print("\n==================================================")
    print("✨ ALL BACKEND PIPELINES INTEGRATED AND SUCCESSFUL! ✨")
    print("==================================================")
    sys.exit(0)

except Exception as e:
    print(f"\n❌ PIPELINE INTEGRATION TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
