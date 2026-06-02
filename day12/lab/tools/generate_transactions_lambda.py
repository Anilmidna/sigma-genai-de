import boto3
import json
import os
import random
from datetime import datetime, timezone, timedelta

# Initialize S3 Client
s3 = boto3.client('s3')

MERCHANTS = ["QuickMart", "FuelPlus", "CafeBlend", "TechZone", "MediPharm",
             "GroceryHub", "PetCorner", "AutoFix", "TravelEasy", "ByteStore"]
CATEGORIES = ["retail", "fuel", "food", "electronics", "pharmacy",
              "grocery", "pet", "automotive", "travel", "tech"]
CURRENCIES = ["INR", "INR", "INR", "INR", "INR", "INR", "USD", "EUR", "INR", "INR"]
STATUSES = ["completed", "completed", "completed", "pending", "failed"]
CITIES = ["Bengaluru", "Mumbai", "Chennai", "Delhi", "Hyderabad", "Pune"]
PAYMENTS = ["UPI", "card", "netbanking", "wallet"]

def rand_date(days_back=7):
    d = datetime.now(timezone.utc) - timedelta(days=random.randint(0, days_back))
    return d.strftime("%Y-%m-%d")

def make_clean_record(idx):
    m = random.randint(0, 9)
    # Generate unique transaction ID
    timestamp_part = datetime.now(timezone.utc).strftime("%y%m%d%H%M%S")
    rand_part = random.randint(1000, 9999)
    return {
        "transaction_id": f"TXN{timestamp_part}{idx:02d}{rand_part}",
        "merchant_name": MERCHANTS[m],
        "category": CATEGORIES[m],
        "amount": round(random.uniform(50, 25000), 2),
        "currency": CURRENCIES[m],
        "transaction_date": rand_date(),
        "status": random.choice(STATUSES),
        "customer_id": f"C{random.randint(1000, 1099)}",
        "payment_method": random.choice(PAYMENTS),
        "merchant_city": random.choice(CITIES),
    }

def inject_disaster_v2(record):
    """
    Renames merchant_name -> merchant_nm, breaks date format (YYYY-MM-DD -> DD-MM-YYYY)
    This replicates the bad Lambda version 2 deployed during the disaster phase.
    """
    record["merchant_nm"] = record.pop("merchant_name", "")
    d = record.get("transaction_date", "")
    if d and '-' in d:
        parts = d.split('-')
        if len(parts) == 3 and len(parts[0]) == 4:
            record["transaction_date"] = f"{parts[2]}-{parts[1]}-{parts[0]}"
    return record

def lambda_handler(event, context):
    bucket_name = event.get('bucket_name', os.environ.get('SIGMA_S3_BUCKET'))
    records_count = int(event.get('records_count', os.environ.get('RECORDS_COUNT', 100)))
    mode = event.get('mode', os.environ.get('GENERATE_MODE', 'clean')).lower()
    
    if not bucket_name:
        return {
            'statusCode': 400,
            'body': 'Error: SIGMA_S3_BUCKET environment variable or event payload value not set.'
        }
        
    print(f"Generating {records_count} records in {mode} mode.")
    
    # 1. Generate the records
    records = []
    for i in range(records_count):
        rec = make_clean_record(i)
        if mode == 'chaos' or mode == 'broken_v2':
            rec = inject_disaster_v2(rec)
        records.append(rec)
        
    # 2. Format as JSON Lines (one JSON object per line)
    json_lines = "\n".join([json.dumps(r) for r in records])
    
    # 3. Construct the hierarchical S3 Bronze folder structure (bronze/YYYY/MM/DD/HH/)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    rand_suffix = random.randint(1000, 9999)
    s3_key = f"bronze/{now.strftime('%Y/%m/%d/%H')}/transactions_{timestamp}_{rand_suffix}.json"
    
    try:
        # 4. Write data to S3 Bronze layer
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json_lines.encode('utf-8')
        )
        print(f"Uploaded {records_count} records to s3://{bucket_name}/{s3_key}")
        return {
            'statusCode': 200,
            'body': {
                'status': 'SUCCESS',
                'records_count': records_count,
                'mode': mode,
                's3_path': f"s3://{bucket_name}/{s3_key}"
            }
        }
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return {
            'statusCode': 500,
            'body': f"Failed to upload to S3: {str(e)}"
        }
