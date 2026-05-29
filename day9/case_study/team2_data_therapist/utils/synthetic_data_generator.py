"""
Synthetic Data Generator for Data Therapist.
Generates realistic but anomaly-ridden transaction data for the Bronze layer.
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_dirty_data(n_records=200, seed=42):
    """
    Generates a DataFrame of dirty transactions representing the raw Bronze layer.
    Intentionally injects realistic data quality issues.
    """
    random.seed(seed)
    np.random.seed(seed)
    
    # Core clean data entities to draw from
    merchant_variations = {
        "Amazon": ["Amazon", "AMAZON", "amazon", "Amazon Inc", "Amazon.com ", " Amazon"],
        "Swiggy": ["Swiggy", "SWIGGY", "swiggy", "Swiggy Delivery", " Swiggy"],
        "Zomato": ["Zomato", "ZOMATO", "zomato", "Zomato Ltd"],
        "Flipkart": ["Flipkart", "FLIPKART", "flipkart", "Flipkart Inc"],
        "Netflix": ["Netflix", "NETFLIX", "netflix", "Netflix Subscription"],
        "Uber": ["Uber", "UBER", "uber", "Uber Rides"],
    }
    
    payment_methods = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "NET_BANKING"]
    regions = ["US", "IN", "EU", "APAC"]
    
    records = []
    
    # Base datetime
    base_date = datetime(2024, 1, 1)
    
    for i in range(1, n_records + 1):
        txn_id = f"TXN{i:03d}"
        cust_id = f"CUST{random.randint(100, 300):03d}"
        
        # Select base merchant and inject spelling variation
        base_merchant = random.choice(list(merchant_variations.keys()))
        merchant_name = random.choice(merchant_variations[base_merchant])
        
        # Decide transaction type and amount
        # Normal purchases: 80%, Refunds: 15%, Chargebacks: 5%
        rand_val = random.random()
        if rand_val < 0.80:
            txn_type = "PURCHASE"
            amount = round(random.uniform(10.0, 1500.0), 2)
        elif rand_val < 0.95:
            txn_type = "REFUND"
            # Refunds are naturally negative representing cash flowing back to the customer
            amount = -round(random.uniform(5.0, 500.0), 2)
        else:
            txn_type = "CHARGEBACK"
            # Chargebacks are also negative adjustments
            amount = -round(random.uniform(20.0, 1000.0), 2)
            
        # Timestamp generation
        delta_seconds = random.randint(0, 30 * 24 * 3600)  # over 30 days
        txn_time = base_date + timedelta(seconds=delta_seconds)
        timestamp_str = txn_time.strftime("%Y-%m-%d %H:%M:%S")
        
        pay_method = random.choice(payment_methods)
        region = random.choice(regions)
        source_system = f"Source_{random.choice(['A', 'B', 'C'])}"
        
        # Standard Record
        record = {
            "transaction_id": txn_id,
            "customer_id": cust_id,
            "merchant_name": merchant_name,
            "transaction_amount": amount,
            "transaction_timestamp": timestamp_str,
            "transaction_type": txn_type,
            "source_system": source_system,
            "payment_method": pay_method,
            "region": region
        }
        records.append(record)
        
    # --- NOW INJECT DATA QUALITY ISSUES INTENTIONALLY ---
    
    # 1. Duplicate Transactions (Duplicate IDs and full records)
    # We duplicate about 8 records
    dup_indices = random.sample(range(len(records)), 8)
    for idx in dup_indices:
        dup_rec = records[idx].copy()
        # Add exact duplicate
        records.append(dup_rec)
        
        # Add duplicate transaction_id but with different amount/timestamp (simulating kafka replay/ingestion retry)
        retry_rec = records[idx].copy()
        retry_rec["transaction_amount"] = round(retry_rec["transaction_amount"] * 1.05, 2)
        retry_rec["transaction_timestamp"] = (datetime.strptime(retry_rec["transaction_timestamp"], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        retry_rec["source_system"] = "Source_B"  # Ingestion retry from Source System B
        records.append(retry_rec)
        
    # 2. Null Values
    # Missing Customer IDs (e.g. 5 records)
    null_cust_indices = random.sample(range(len(records)), 5)
    for idx in null_cust_indices:
        records[idx]["customer_id"] = None
        
    # Null Merchant Names (e.g. 4 records)
    null_merch_indices = random.sample(range(len(records)), 4)
    for idx in null_merch_indices:
        records[idx]["merchant_name"] = None
        
    # Null Transaction IDs (schema inconsistency or ingestion breakdown, e.g. 3 records)
    null_id_indices = random.sample(range(len(records)), 3)
    for idx in null_id_indices:
        records[idx]["transaction_id"] = None

    # 3. Invalid Timestamps
    # Malformed timestamp strings (e.g. '15/01/2024' or '2024.01.12')
    malformed_time_indices = random.sample(range(len(records)), 5)
    for count, idx in enumerate(malformed_time_indices):
        orig_time = datetime.strptime(records[idx]["transaction_timestamp"], "%Y-%m-%d %H:%M:%S")
        if count % 2 == 0:
            records[idx]["transaction_timestamp"] = orig_time.strftime("%d-%m-%Y")
        else:
            records[idx]["transaction_timestamp"] = orig_time.strftime("%Y/%m/%d %H:%M")
            
    # Impossible/Future Timestamps (e.g. '2099-12-31 23:59:59')
    impossible_time_indices = random.sample(range(len(records)), 3)
    for idx in impossible_time_indices:
        records[idx]["transaction_timestamp"] = "2099-12-31 23:59:59"
        
    # 4. Outlier Transaction Amounts
    # e.g., standard consumer transactions shouldn't be $5,000,000.00
    outlier_indices = random.sample(range(len(records)), 2)
    for idx in outlier_indices:
        records[idx]["transaction_amount"] = 5000000.00 if random.random() > 0.5 else -2500000.00
        
    # 5. Invalid Transaction Types (e.g. 'UNKNOWN' or 'COMPLETED' mixed into transaction_type)
    invalid_type_indices = random.sample(range(len(records)), 3)
    for idx in invalid_type_indices:
        records[idx]["transaction_type"] = "SUCCESS" if random.random() > 0.5 else "PENDING"
        
    # Shuffle the dataset to mix the injected errors
    random.shuffle(records)
    
    df = pd.DataFrame(records)
    return df

if __name__ == "__main__":
    df = generate_dirty_data()
    print(f"Generated {len(df)} transactions.")
    print("Columns:", df.columns.tolist())
    print("\nNull Counts:")
    print(df.isnull().sum())
    print("\nSample records:")
    print(df.head(10))
