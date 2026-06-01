"""
==============================================================================
DAY 13 — SIGMA DATATECH DATA GENERATOR
==============================================================================
Simulates Sigma DataTech's merchant transaction feed into Kinesis.

Modes:
  --mode clean           → valid, well-formed records
  --mode chaos           → inject specific pain points (use --inject flag)

Inject options (use with --mode chaos):
  --inject schema_drift  → adds upi_ref_id, device_fingerprint; renames merchant_name → merchant_nm
  --inject pii_leak      → adds cust_ph, acct_no, emp_pncd in plain text
  --inject quality_rot   → null PKs, negative amounts, bad dates, unknown currencies
  --inject all           → all three combined

Usage:
  python data_generator.py --mode clean --records 200 --stream sigma-transactions
  python data_generator.py --mode chaos --inject schema_drift --records 100
  python data_generator.py --mode chaos --inject all --records 500

==============================================================================
"""

import argparse, boto3, json, random, time, sys
from datetime import datetime, timedelta

random.seed()  # different seed each run so outputs differ per team

# ── Config ────────────────────────────────────────────────────────────────────
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
UPI_REFS    = [f"UPI-{random.randint(1000,9999)}-{random.randint(1000,9999)}" for _ in range(50)]
DEVICE_FPS  = [f"FP-{random.randint(100000,999999)}" for _ in range(50)]

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
    """Rename merchant_name → merchant_nm, add 2 new columns."""
    record["merchant_nm"] = record.pop("merchant_name")
    record["upi_ref_id"]         = random.choice(UPI_REFS)
    record["device_fingerprint"] = random.choice(DEVICE_FPS)
    return record

def inject_pii_leak(record):
    """Add PII columns with abbreviated names."""
    record["cust_ph"]  = random.choice(PHONES)
    record["acct_no"]  = random.choice(ACCT_NOS)
    record["emp_pncd"] = random.choice(PIN_CODES)
    return record

def inject_quality_rot(record, idx, n_records):
    """Inject quality issues across the batch."""
    rot_type = random.random()
    pct = idx / n_records
    if pct < 0.06:                    # 6% null PKs
        record["transaction_id"] = ""
    elif pct < 0.10:                  # 4% negative amounts
        record["amount"] = -abs(record["amount"])
    elif pct < 0.125:                 # 2.5% bad dates
        record["transaction_date"] = "99-99-9999"
    elif pct < 0.14:                  # 1.5% unknown currency
        record["currency"] = "XYZ"
    return record

def send_to_kinesis(client, stream_name, record, verbose=True):
    """Send one record to Kinesis."""
    data = json.dumps(record).encode("utf-8")
    resp = client.put_record(
        StreamName=stream_name,
        Data=data,
        PartitionKey=record.get("transaction_id", "default") or "default",
    )
    if verbose:
        tid  = record.get("transaction_id") or record.get("transaction_id", "NULL")
        name = record.get("merchant_name") or record.get("merchant_nm", "?")
        amt  = record.get("amount", 0)
        curr = record.get("currency", "?")
        status = resp["ResponseMetadata"]["HTTPStatusCode"]
        mark = "[OK]" if status == 200 else "[ERR]"
        print(f"  {mark} {str(tid):12} | {name:12} | {curr} {float(amt):>10,.2f}")
    return resp["ResponseMetadata"]["HTTPStatusCode"] == 200

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Sigma DataTech Kinesis Data Generator")
    parser.add_argument("--mode",    choices=["clean","chaos"], default="clean")
    parser.add_argument("--inject",  choices=["schema_drift","pii_leak","quality_rot","all"], default=None)
    parser.add_argument("--records", type=int, default=200)
    parser.add_argument("--stream",  default="sigma-transactions")
    parser.add_argument("--region",  default="us-east-1")
    parser.add_argument("--delay",   type=float, default=0.05, help="Seconds between records")
    args = parser.parse_args()

    if args.mode == "chaos" and args.inject is None:
        print("[ERROR] --mode chaos requires --inject flag")
        print("        Options: schema_drift / pii_leak / quality_rot / all")
        sys.exit(1)

    print("=" * 60)
    print("SIGMA DATATECH — KINESIS DATA GENERATOR")
    print("=" * 60)
    print(f"  Mode   : {args.mode.upper()}")
    if args.inject:
        print(f"  Inject : {args.inject.upper()}")
    print(f"  Records: {args.records}")
    print(f"  Stream : {args.stream}")
    print(f"  Region : {args.region}")
    print("=" * 60)

    try:
        client = boto3.client("kinesis", region_name=args.region)
        # Quick check — will raise if credentials or stream don't exist
        client.describe_stream_summary(StreamName=args.stream)
    except Exception as e:
        print(f"[ERROR] Cannot connect to Kinesis stream '{args.stream}': {e}")
        print("        Check: aws kinesis list-streams --region", args.region)
        sys.exit(1)

    sent = 0
    errors = 0
    start = time.time()

    for i in range(args.records):
        record = make_clean_record(i)

        if args.mode == "chaos":
            inj = args.inject
            if inj == "schema_drift" or inj == "all":
                record = inject_schema_drift(record)
            if inj == "pii_leak" or inj == "all":
                record = inject_pii_leak(record)
            if inj == "quality_rot" or inj == "all":
                record = inject_quality_rot(record, i, args.records)

        # Only print every 10th record to keep output readable
        verbose = (i % 10 == 0)
        ok = send_to_kinesis(client, args.stream, record, verbose=verbose)
        if ok:
            sent += 1
        else:
            errors += 1

        time.sleep(args.delay)

    elapsed = round(time.time() - start, 1)
    print("=" * 60)
    print(f"  DONE in {elapsed}s")
    print(f"  Sent  : {sent} records")
    print(f"  Errors: {errors} records")
    if args.mode == "chaos":
        print()
        if args.inject in ("schema_drift", "all"):
            print("  SCHEMA DRIFT injected:")
            print("    merchant_name → merchant_nm (renamed)")
            print("    + upi_ref_id, device_fingerprint (new columns)")
        if args.inject in ("pii_leak", "all"):
            print("  PII LEAK injected:")
            print("    + cust_ph (phone), acct_no (account), emp_pncd (PIN)")
        if args.inject in ("quality_rot", "all"):
            est_bad = round(args.records * 0.14)
            print("  QUALITY ROT injected:")
            print(f"    ~{round(args.records*0.06)} null transaction_ids")
            print(f"    ~{round(args.records*0.04)} negative amounts")
            print(f"    ~{round(args.records*0.025)} bad dates (99-99-9999)")
            print(f"    ~{round(args.records*0.015)} unknown currencies (XYZ)")
            print(f"    ~{est_bad} total bad records out of {args.records}")
    print("=" * 60)
    print(f"  Firehose delivers to S3 in ~60-90 seconds.")
    print(f"  Watch: aws s3 ls s3://<your-bucket>/bronze/ --recursive")
    print("=" * 60)

if __name__ == "__main__":
    main()
