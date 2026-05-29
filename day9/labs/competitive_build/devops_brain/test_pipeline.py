import sys
import os
import pytest
from sample_data import transform_bronze_to_silver, compute_merchant_performance, compute_daily_summary, TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY, MERCHANTS

sys.path.insert(0, os.path.dirname(__file__) + "/../")
sys.path.insert(0, os.path.dirname(__file__) + "/../../")

def test_null_transaction_id_filtered():
    """Guards against null transaction IDs reaching silver layer."""
    transactions = [{"transaction_id": None, "amount": 100.0, "merchant_id": "M001"}]
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert len(silver) == 0

def test_negative_amount_filtered():
    """Guards against negative amounts reaching silver layer."""
    transactions = [{"transaction_id": "TXN001", "amount": -50.0, "merchant_id": "M001"}]
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert len(silver) == 0

def test_duplicate_transaction_id_deduplicated():
    """Guards against duplicate transaction IDs in silver layer."""
    transactions = [{"transaction_id": "TXN012", "amount": 100.0, "merchant_id": "M001"}] * 2
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert len(silver) == 1

def test_merchant_enrichment_clean_record():
    """Guards against merchant enrichment failure for clean records."""
    transactions = [{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "M001", "status": "COMPLETED"}]
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert silver[0]["merchant_name"] == "Merchant 1"
    assert silver[0]["category"] == "Retail"
    assert silver[0]["city"] == "City 1"

def test_unmatched_merchant_gets_flag():
    """Guards against unmatched merchants not getting UNMATCHED flag."""
    transactions = [{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "MXXX", "status": "COMPLETED"}]
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert silver[0]["quality_flag"] == "UNMATCHED"

def test_revenue_counts_only_completed():
    """Guards against FAILED transactions contributing to total_revenue."""
    silver_rows = [{"merchant_id": "M001", "amount": 100.0, "status": "FAILED"}]
    performance = compute_merchant_performance(silver_rows)
    assert performance[0]["total_revenue"] == 0.0

def test_failure_rate_calculation():
    """Guards against incorrect failure rate calculation."""
    silver_rows = [
        {"merchant_id": "M001", "amount": 100.0, "status": "COMPLETED"},
        {"merchant_id": "M001", "amount": 50.0, "status": "FAILED"}
    ]
    performance = compute_merchant_performance(silver_rows)
    assert performance[0]["failure_rate_pct"] == 50.0

def test_merchant_performance_wrong_assertion():
    """INTENTIONAL BUG: this test passes but proves nothing"""
    silver_rows = [{"merchant_id": "M001", "amount": 0.0, "status": "COMPLETED"}]
    performance = compute_merchant_performance(silver_rows)
    assert performance[0]["total_revenue"] == 0.0  # INTENTIONAL BUG: this test passes but proves nothing

def test_unique_customer_count_per_date():
    """Guards against incorrect unique customer count per date."""
    silver_rows = [
        {"transaction_date": "2024-01-15", "customer_id": "C001", "merchant_id": "M001"},
        {"transaction_date": "2024-01-15", "customer_id": "C002", "merchant_id": "M001"}
    ]
    summary = compute_daily_summary(silver_rows)
    assert summary[0]["unique_customers"] == 2