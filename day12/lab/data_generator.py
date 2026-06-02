"""
Sigma DataTech Data Generator
Writes transaction records to S3 Bronze and directly to Snowflake.
No Kinesis or Firehose required.

Modes:
  --mode clean           → valid, well-formed records
  --mode chaos           → inject specific pain points

Inject options (use with --mode chaos):
  --inject schema_drift  → renames merchant_name → merchant_nm
  --inject pii_leak      → adds cust_ph, acct_no in plain text
  --inject quality_rot   → null PKs, negative amounts, bad dates

Usage:
  python lab/data_generator.py --mode clean --records 100
  python lab/data_generator.py --mode chaos --inject schema_drift --records 100
"""

import argparse, boto3, json, os, random, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

REGION  = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BUCKET  = os.getenv("SIGMA_S3_BUCKET", "")

MERCHANTS   = ["QuickMart","FuelPlus","CafeBlend","TechZone","MediPharm",
               "GroceryHub","PetCorner","AutoFix","TravelEasy","ByteStore"]
CATEGORIES  = ["retail","fuel","food","electronics","pharmacy",
               "grocery","pet","automotive","travel","tech"]
CURRENCIES  = ["INR","INR","INR","INR","INR","INR","USD","EUR","INR","INR"]
STATUSES    = ["completed","completed","completed","pending","failed"]
CITIES      = ["Bengaluru","Mumbai","Chennai","Delhi","Hyderabad","Pune"]
PAYMENTS    = ["UPI","card","netbanking","wallet"]
PHONES      = [f"+91{random.randint(7000000000,9999999999)}" for _ in range(50)]
ACCT_NOS    = [f"{random.randint(100000000000,999999999999)}" for _ in range(50)]
PIN_CODES   = ["560001","400001","600001","110001","500001"]


def rand_date(days_back=7):
    d = datetime.now() - timedelta(days=random.randint(0, days_back))
    return d.strftime("%Y-%m-%d")


def make_clean_record(idx):
    m = random.randint(0, 9)
    return {
        "transaction_id":   f"TXN{100000 + idx}",
        "merchant_name":    MERCHANTS[m],
        "category":         CATEGORIES[m],
        "amount":           round(random.uniform(50, 25000), 2),
        "currency":         CURRENCIES[m],
        "transaction_date": rand_date(),
        "status":           random.choice(STATUSES),
        "customer_id":      f"C{random.randint(1000,1099)}",
        "payment_method":   random.choice(PAYMENTS),
        "merchant_city":    random.choice(CITIES),
    }


def inject_schema_drift(record):
    record["merchant_nm"] = record.pop("merchant_name")
    return record


def inject_pii_leak(record):
    record["cust_ph"] = random.choice(PHONES)
    record["acct_no"] = random.choice(ACCT_NOS)
    return record


def inject_quality_rot(record, idx, n_records):
    pct = idx / n_records
    if pct < 0.06:
        record["transaction_id"] = ""
    elif pct < 0.10:
        record["amount"] = -abs(record["amount"])
    elif pct < 0.125:
        record["transaction_date"] = "99-99-9999"
    return record


def write_to_s3(s3, records, mode):
    if not BUCKET:
        print("  [WARN] SIGMA_S3_BUCKET not set — skipping S3 write")
        return None
    prefix = f"bronze/{mode}/{datetime.utcnow().strftime('%Y/%m/%d/%H')}/"
    key    = f"{prefix}batch_{int(time.time())}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(records).encode(),
        ContentType="application/json",
    )
    return f"s3://{BUCKET}/{key}"


def write_to_snowflake(records):
    try:
        import snowflake.connector
    except ImportError:
        print("  [WARN] snowflake-connector-python not installed — skipping Snowflake write")
        return 0

    account   = os.getenv("SNOWFLAKE_ACCOUNT", "")
    user      = os.getenv("SNOWFLAKE_USER", "")
    password  = os.getenv("SNOWFLAKE_PASSWORD", "")
    database  = os.getenv("SNOWFLAKE_DATABASE", "SIGMA")
    schema    = os.getenv("SNOWFLAKE_SCHEMA", "SILVER")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH")

    if not all([account, user, password]):
        print("  [WARN] Snowflake credentials not set — skipping Snowflake write")
        return 0

    try:
        conn = snowflake.connector.connect(
            account=account, user=user, password=password,
            database=database, schema=schema, warehouse=warehouse,
        )
        cur = conn.cursor()
        ts  = datetime.utcnow().isoformat()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS TRANSACTIONS (
                transaction_id   VARCHAR,
                merchant_name    VARCHAR,
                category         VARCHAR,
                amount           FLOAT,
                currency         VARCHAR,
                transaction_date DATE,
                status           VARCHAR,
                customer_id      VARCHAR,
                payment_method   VARCHAR,
                merchant_city    VARCHAR,
                _loaded_at       TIMESTAMP_TZ
            )
        """)

        cur.execute("""
            CREATE TEMPORARY TABLE IF NOT EXISTS temp_gen (
                transaction_id VARCHAR, merchant_name VARCHAR, category VARCHAR,
                amount FLOAT, currency VARCHAR, transaction_date DATE,
                status VARCHAR, customer_id VARCHAR, payment_method VARCHAR,
                merchant_city VARCHAR, _loaded_at TIMESTAMP_TZ
            )
        """)

        batch = [
            (r.get("transaction_id",""), r.get("merchant_name",""),
             r.get("category",""), float(r.get("amount",0) or 0),
             r.get("currency","INR"), r.get("transaction_date",""),
             r.get("status",""), r.get("customer_id",""),
             r.get("payment_method",""), r.get("merchant_city",""), ts)
            for r in records if r.get("transaction_id")
        ]

        cur.executemany(
            "INSERT INTO temp_gen VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            batch,
        )

        cur.execute(f"""
            MERGE INTO {database}.{schema}.TRANSACTIONS AS t
            USING temp_gen AS s ON t.transaction_id = s.transaction_id
            WHEN NOT MATCHED THEN INSERT (
                transaction_id, merchant_name, category, amount, currency,
                transaction_date, status, customer_id, payment_method,
                merchant_city, _loaded_at
            ) VALUES (
                s.transaction_id, s.merchant_name, s.category, s.amount,
                s.currency, s.transaction_date, s.status, s.customer_id,
                s.payment_method, s.merchant_city, s._loaded_at
            )
        """)

        cur.execute("SELECT COUNT(*) FROM temp_gen")
        loaded = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return loaded

    except Exception as e:
        print(f"  [WARN] Snowflake write failed: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode",    choices=["clean","chaos"], default="clean")
    parser.add_argument("--inject",  choices=["schema_drift","pii_leak","quality_rot","all"], default=None)
    parser.add_argument("--records", type=int, default=100)
    parser.add_argument("--stream",  default=None, help="ignored — kept for compatibility")
    parser.add_argument("--region",  default=REGION)
    args = parser.parse_args()

    if args.mode == "chaos" and args.inject is None:
        print("[ERROR] --mode chaos requires --inject flag")
        sys.exit(1)

    print("=" * 60)
    print("SIGMA DATATECH — DATA GENERATOR")
    print("=" * 60)
    print(f"  Mode   : {args.mode.upper()}")
    if args.inject:
        print(f"  Inject : {args.inject.upper()}")
    print(f"  Records: {args.records}")
    print(f"  Bucket : {BUCKET or '(not set)'}")
    print("=" * 60)

    s3      = boto3.client("s3", region_name=args.region)
    records = []

    for i in range(args.records):
        rec = make_clean_record(i)
        if args.mode == "chaos":
            if args.inject in ("schema_drift", "all"):
                rec = inject_schema_drift(rec)
            if args.inject in ("pii_leak", "all"):
                rec = inject_pii_leak(rec)
            if args.inject in ("quality_rot", "all"):
                rec = inject_quality_rot(rec, i, args.records)
        records.append(rec)

        # Print every 10th record
        if i % 10 == 0:
            name = rec.get("merchant_name") or rec.get("merchant_nm","?")
            amt  = rec.get("amount", 0)
            tid  = rec.get("transaction_id","NULL") or "NULL"
            print(f"  [OK] {str(tid):12} | {name:12} | INR {float(amt):>10,.2f}")

    print("=" * 60)

    # Write to S3
    s3_path = write_to_s3(s3, records, args.mode)
    if s3_path:
        print(f"  S3   : {s3_path}")

    # Load to Snowflake (clean mode only — chaos is for investigation scenarios)
    if args.mode == "clean":
        loaded = write_to_snowflake(records)
        print(f"  Snowflake: {loaded} rows loaded (MERGE INTO)")

    print("=" * 60)
    print(f"  Done. {len(records)} records processed.")
    if args.mode == "clean":
        print(f"  Run: python lab/investigate/check_snowflake.py to verify.")
    print("=" * 60)


if __name__ == "__main__":
    main()
