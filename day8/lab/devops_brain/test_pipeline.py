import sys
import os
sys.path.insert(0, os.path.dirname(__file__) + "/../")
sys.path.insert(0, os.path.dirname(__file__) + "/../../")
from sample_data import transform_bronze_to_silver, compute_merchant_performance, compute_daily_summary, TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY, MERCHANTS

def test_null_transaction_id_filtered():
    """Ensure transactions with null IDs are filtered out."""
    silver = transform_bronze_to_silver([{"transaction_id": None, "amount": 100.0, "merchant_id": "M001"}], MERCHANTS)
    assert len(silver) == 0

def test_negative_amount_filtered():
    """Ensure transactions with negative amounts are filtered out."""
    silver = transform_bronze_to_silver([{"transaction_id": "TXN001", "amount": -50.0, "merchant_id": "M001"}], MERCHANTS)
    assert len(silver) == 0

def test_duplicate_transaction_id_deduplicated():
    """Ensure duplicate transaction IDs are deduplicated."""
    transactions = [{"transaction_id": "TXN012", "amount": 100.0, "merchant_id": "M001"}] * 2
    silver = transform_bronze_to_silver(transactions, MERCHANTS)
    assert len(silver) == 1

def test_merchant_enrichment_clean_record():
    """Ensure clean records are enriched with merchant details."""
    silver = transform_bronze_to_silver([{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "M001"}], MERCHANTS)
    assert silver[0]["merchant_name"] == "Merchant 1"
    assert silver[0]["category"] == "Retail"
    assert silver[0]["city"] == "City 1"

def test_unmatched_merchant_gets_flag():
    """Ensure unmatched merchants get UNMATCHED flag."""
    silver = transform_bronze_to_silver([{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "MXXX"}], MERCHANTS)
    assert silver[0]["quality_flag"] == "UNMATCHED"

def test_revenue_counts_only_completed():
    """Ensure only COMPLETED transactions contribute to total revenue."""
    silver = [{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "M001", "status": "COMPLETED"},
              {"transaction_id": "TXN002", "amount": 50.0, "merchant_id": "M001", "status": "FAILED"}]
    performance = compute_merchant_performance(silver)
    assert performance[0]["total_revenue"] == 100.0

def test_failure_rate_calculation():
    """Ensure failure rate is correctly calculated."""
    silver = [{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "M001", "status": "COMPLETED"},
              {"transaction_id": "TXN002", "amount": 50.0, "merchant_id": "M001", "status": "FAILED"}]
    performance = compute_merchant_performance(silver)
    assert performance[0]["failure_rate_pct"] == 50.0

def test_merchant_performance_wrong_assertion():
    """INTENTIONAL BUG: this test passes but proves nothing"""
    silver = [{"transaction_id": "TXN001", "amount": 0.0, "merchant_id": "M001", "status": "COMPLETED"}]
    performance = compute_merchant_performance(silver)
    assert performance[0]["total_revenue"] == 0.0

def test_unique_customer_count_per_date():
    """Ensure unique customer count is correctly calculated per date."""
    silver = [{"transaction_id": "TXN001", "amount": 100.0, "merchant_id": "M001", "customer_id": "C001", "transaction_date": "2024-01-15"},
              {"transaction_id": "TXN002", "amount": 50.0, "merchant_id": "M001", "customer_id": "C002", "transaction_date": "2024-01-15"}]
    summary = compute_daily_summary(silver)
    assert summary[0]["unique_customers"] == 2