"""
Synthetic Data Generator — Data Therapist
Generates a realistic dirty Bronze-layer transaction dataset for Sigma DataTech.
"""

import pandas as pd
import random
from datetime import datetime, timedelta


VALID_STATUSES = ["COMPLETED", "FAILED", "PENDING"]
PAYMENT_METHODS = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]
SOURCE_SYSTEMS = ["SYS_A", "SYS_B", "SYS_C"]
REGIONS = ["NORTH", "SOUTH", "EAST", "WEST", "CENTRAL"]
TRANSACTION_TYPES = ["PURCHASE", "REFUND", "CHARGEBACK", "TRANSFER"]

# Merchant names with intentional inconsistencies (the trap!)
MERCHANT_VARIANTS = {
    "Amazon": ["Amazon", "AMAZON", "amazon", "Amazon Inc", "Amazon.in", "AMAZON INC"],
    "Swiggy": ["Swiggy", "SWIGGY", "Swiggy Food", "swiggy"],
    "Zomato": ["Zomato", "ZOMATO", "Zomato India", "zomato"],
    "Ola": ["Ola", "OLA", "Ola Cabs", "OLA Cabs"],
    "Flipkart": ["Flipkart", "FLIPKART", "Flipkart India"],
    "BigBasket": ["BigBasket", "Big Basket", "BIGBASKET", "bigbasket"],
    "MakeMyTrip": ["MakeMyTrip", "Make My Trip", "MAKEMYTRIP"],
    "BookMyShow": ["BookMyShow", "Book My Show", "BOOKMYSHOW"],
}

MERCHANT_LIST = list(MERCHANT_VARIANTS.keys())


def generate_clean_transactions(n=80):
    """Generate clean, valid transactions."""
    rows = []
    base_date = datetime(2024, 1, 15)
    for i in range(n):
        txn_date = base_date + timedelta(days=random.randint(0, 45))
        merchant = random.choice(MERCHANT_LIST)
        txn_type = random.choice(TRANSACTION_TYPES)
        amount = round(random.uniform(50, 5000), 2)
        if txn_type == "REFUND":
            amount = -abs(amount)  # Refunds are legitimately negative

        rows.append({
            "transaction_id": f"TXN{str(i + 1).zfill(4)}",
            "customer_id": f"CUST{random.randint(1, 30):03d}",
            "merchant_name": random.choice(MERCHANT_VARIANTS[merchant]),
            "transaction_amount": amount,
            "transaction_timestamp": txn_date.strftime("%Y-%m-%d %H:%M:%S"),
            "transaction_type": txn_type,
            "source_system": random.choice(SOURCE_SYSTEMS),
            "payment_method": random.choice(PAYMENT_METHODS),
            "region": random.choice(REGIONS),
            "status": random.choice(VALID_STATUSES),
        })
    return rows


def inject_quality_issues(rows):
    """Inject realistic data quality problems into the dataset."""
    dirty = list(rows)  # copy
    n = len(dirty)

    # Issue 1: Duplicate transaction IDs (Kafka replay / retry — TRAP!)
    dupe_indices = random.sample(range(10, 30), 5)
    for idx in dupe_indices:
        dup = dict(dirty[idx])
        dirty.append(dup)  # exact duplicate → dedup fix looks safe but...

    # Issue 2: Null merchant names (missing data from SYS_C)
    null_merchant_indices = random.sample(range(n), 8)
    for idx in null_merchant_indices:
        dirty[idx]["merchant_name"] = None

    # Issue 3: Negative amounts that are NOT refunds (data entry errors)
    #   THE TRAP: "convert negatives to positives" fix will also flip real refunds!
    non_refund_indices = [i for i, r in enumerate(dirty) if r["transaction_type"] != "REFUND"]
    neg_indices = random.sample(non_refund_indices, 6)
    for idx in neg_indices:
        dirty[idx]["transaction_amount"] = -abs(dirty[idx]["transaction_amount"])

    # Issue 4: Malformed / impossible timestamps
    bad_ts_indices = random.sample(range(n), 4)
    bad_timestamps = [
        "2099-12-31 23:59:59",  # future date
        "2024-13-45 00:00:00",  # invalid month/day
        "not-a-date",           # completely malformed
        "0000-00-00 00:00:00",  # epoch zero
    ]
    for i, idx in enumerate(bad_ts_indices):
        dirty[idx]["transaction_timestamp"] = bad_timestamps[i]

    # Issue 5: Missing customer IDs
    null_cust_indices = random.sample(range(n), 7)
    for idx in null_cust_indices:
        dirty[idx]["customer_id"] = None

    # Issue 6: Invalid transaction types
    invalid_types = ["APPROVED", "CANCELLED", "VOID", "RETRY", "UNKNOWN"]
    invalid_type_indices = random.sample(range(n), 5)
    for idx in invalid_type_indices:
        dirty[idx]["transaction_type"] = random.choice(invalid_types)

    # Issue 7: Missing transaction IDs (null IDs)
    null_id_indices = random.sample(range(n), 4)
    for idx in null_id_indices:
        dirty[idx]["transaction_id"] = None

    # Issue 8: Whitespace issues in merchant names
    ws_indices = random.sample(range(n), 5)
    for idx in ws_indices:
        if dirty[idx]["merchant_name"]:
            dirty[idx]["merchant_name"] = "  " + dirty[idx]["merchant_name"] + "  "

    # Issue 9: Extreme outlier amounts (possible fraud signals)
    outlier_indices = random.sample(range(n), 3)
    for idx in outlier_indices:
        dirty[idx]["transaction_amount"] = round(random.uniform(500000, 2000000), 2)

    # Issue 10: Invalid source system codes
    invalid_sys_indices = random.sample(range(n), 4)
    for idx in invalid_sys_indices:
        dirty[idx]["source_system"] = random.choice(["SYS_X", "UNKNOWN", "", "NULL_SYS"])

    return dirty


def generate_bronze_dataset():
    """Generate the full Bronze-layer dirty dataset."""
    clean = generate_clean_transactions(80)
    dirty = inject_quality_issues(clean)
    df = pd.DataFrame(dirty)

    # Shuffle for realism
    df = df.sample(frac=1).reset_index(drop=True)
    return df


if __name__ == "__main__":
    df = generate_bronze_dataset()
    print(f"Generated {len(df)} Bronze rows")
    print(df.head(10))
    print("\nNull counts:")
    print(df.isnull().sum())
