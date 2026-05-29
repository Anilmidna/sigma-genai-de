from datetime import datetime, timedelta

def filter_recent_transactions(transactions, cutoff_date):
    return [t for t in transactions if t['date'] > cutoff_date]

def apply_silver_rules(transactions):
    return [t for t in transactions if t.get('transaction_id') and t.get('amount') >= 0]

import pytest

def test_filter_recent_transactions_boundary():
    cutoff_date = datetime.now() - timedelta(days=1)
    transactions = [
        {'date': cutoff_date, 'amount': 100},
        {'date': cutoff_date + timedelta(seconds=1), 'amount': 200},
        {'date': cutoff_date - timedelta(days=1), 'amount': 300},
    ]
    expected = [{'date': cutoff_date + timedelta(seconds=1), 'amount': 200}]
    assert filter_recent_transactions(transactions, cutoff_date) == expected

def test_apply_silver_rules_filter_none_transaction_id():
    transactions = [
        {'transaction_id': 1, 'amount': 100},
        {'transaction_id': None, 'amount': 200},
        {'transaction_id': 3, 'amount': 300},
    ]
    expected = [
        {'transaction_id': 1, 'amount': 100},
        {'transaction_id': 3, 'amount': 300},
    ]
    assert apply_silver_rules(transactions) == expected

def test_apply_silver_rules_filter_negative_amount():
    transactions = [
        {'transaction_id': 1, 'amount': 100},
        {'transaction_id': 2, 'amount': -200},
        {'transaction_id': 3, 'amount': 300},
    ]
    expected = [
        {'transaction_id': 1, 'amount': 100},
        {'transaction_id': 3, 'amount': 300},
    ]
    assert apply_silver_rules(transactions) == expected