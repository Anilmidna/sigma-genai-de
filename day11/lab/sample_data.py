"""
==============================================================================
DAY 11 — SAMPLE DATA GENERATOR
==============================================================================
Generates realistic-but-messy CSVs for Sigma DataTech's ingestion quality
agent labs.  Run this FIRST — all other Day 11 scripts depend on these files.

OUTPUT FILES
------------
  data/transactions_raw.csv      — main dataset with intentional quality issues
  data/customers_raw.csv         — customer PII dataset (names, emails, phones)
  data/transactions_clean.csv    — clean reference (for stretch goal comparison)
==============================================================================
"""

import os, csv, random, json
from datetime import datetime, timedelta

random.seed(42)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
def rand_date(start_days_ago=90):
    base = datetime.now() - timedelta(days=start_days_ago)
    return (base + timedelta(days=random.randint(0, start_days_ago))).strftime("%Y-%m-%d")

MERCHANTS = [
    "QuickMart", "FuelPlus", "CafeBlend", "TechZone", "MediPharm",
    "GroceryHub", "PetCorner", "AutoFix", "TravelEasy", "ByteStore"
]
CATEGORIES = ["retail", "fuel", "food", "electronics", "pharmacy",
              "grocery", "pet", "automotive", "travel", "tech"]
CURRENCIES = ["INR", "USD", "EUR", "INR", "INR", "INR", "INR", "INR", "INR", "INR"]
STATUSES   = ["completed", "completed", "completed", "pending", "failed", "completed", "completed"]

def make_txn_row(i, inject_issues=True):
    merchant_idx = random.randint(0, 9)
    amount = round(random.uniform(10, 50000), 2)
    row = {
        "transaction_id": f"TXN{100000 + i}",
        "merchant_name":  MERCHANTS[merchant_idx],
        "category":       CATEGORIES[merchant_idx],
        "amount":         amount,
        "currency":       CURRENCIES[merchant_idx],
        "transaction_date": rand_date(),
        "status":         random.choice(STATUSES),
        "customer_id":    f"C{random.randint(1000, 1099)}",
        "payment_method": random.choice(["UPI", "card", "netbanking", "wallet"]),
        "merchant_city":  random.choice(["Bengaluru", "Mumbai", "Chennai", "Delhi", "Hyderabad"]),
    }

    if inject_issues:
        r = random.random()
        if r < 0.04:   row["transaction_id"] = ""           # blank PK
        elif r < 0.07: row["amount"] = ""                   # null amount
        elif r < 0.09: row["amount"] = -abs(amount)         # negative amount
        elif r < 0.11: row["transaction_date"] = "99-99-9999"  # bad date
        elif r < 0.13: row["currency"] = "XYZ"              # unknown currency
        elif r < 0.14: row["amount"] = 9999999              # outlier amount
        elif r < 0.15: row["merchant_name"] = ""            # blank merchant

    return row

def make_customer_row(i):
    cid = f"C{1000 + i}"
    first = random.choice(["Amit", "Priya", "Rahul", "Sneha", "Vikram", "Ananya", "Rohit", "Kavya"])
    last  = random.choice(["Sharma", "Patel", "Kumar", "Singh", "Nair", "Iyer", "Reddy", "Joshi"])
    return {
        "customer_id":    cid,
        "full_name":      f"{first} {last}",
        "email_address":  f"{first.lower()}.{last.lower()}{random.randint(1,99)}@gmail.com",
        "phone_number":   f"+91{random.randint(7000000000, 9999999999)}",
        "pan_number":     f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ',k=5))}{random.randint(1000,9999)}{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ',k=1))}",
        "account_number": f"{random.randint(100000000000, 999999999999)}",
        "city":           random.choice(["Bengaluru", "Mumbai", "Chennai", "Delhi", "Hyderabad"]),
        "kyc_status":     random.choice(["verified", "verified", "pending", "rejected"]),
        "created_date":   rand_date(365),
    }

# ── Generate transactions_raw.csv (messy) ────────────────────────────────────
txn_fields = ["transaction_id","merchant_name","category","amount","currency",
              "transaction_date","status","customer_id","payment_method","merchant_city"]

txn_path = os.path.join(DATA_DIR, "transactions_raw.csv")
with open(txn_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=txn_fields)
    w.writeheader()
    for i in range(1, 501):
        w.writerow(make_txn_row(i, inject_issues=True))

# ── Generate transactions_clean.csv (reference) ──────────────────────────────
clean_path = os.path.join(DATA_DIR, "transactions_clean.csv")
with open(clean_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=txn_fields)
    w.writeheader()
    for i in range(501, 701):
        w.writerow(make_txn_row(i, inject_issues=False))

# ── Generate customers_raw.csv (PII) ─────────────────────────────────────────
cust_fields = ["customer_id","full_name","email_address","phone_number",
               "pan_number","account_number","city","kyc_status","created_date"]

cust_path = os.path.join(DATA_DIR, "customers_raw.csv")
with open(cust_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cust_fields)
    w.writeheader()
    for i in range(100):
        w.writerow(make_customer_row(i))

# ── Print summary ─────────────────────────────────────────────────────────────
print("=" * 60)
print("SIGMA DATATECH — DAY 11 SAMPLE DATA GENERATED")
print("=" * 60)
print(f"  transactions_raw.csv  : 500 rows (with quality issues)")
print(f"  transactions_clean.csv: 200 rows (clean reference)")
print(f"  customers_raw.csv     : 100 rows (PII data)")
print()
print("Known issues injected in transactions_raw.csv:")
print("  • Blank transaction_id (PK nulls)")
print("  • Null / negative amounts")
print("  • Invalid date formats (99-99-9999)")
print("  • Unknown currency codes (XYZ)")
print("  • Extreme outlier amounts")
print("  • Blank merchant names")
print()
print("Run scripts in order: 1 → 2 → 3 → 4 (stretch)")
