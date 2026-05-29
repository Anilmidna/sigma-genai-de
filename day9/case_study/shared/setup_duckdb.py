"""
Day 9 — DuckDB Setup
Run once before any team app: python shared/setup_duckdb.py

Creates sigma_platform.duckdb with Bronze/Silver/Gold + all team-specific tables.
"""
import sys, os
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import duckdb
from sample_data import (
    TRANSACTIONS_CLEAN, TRANSACTIONS_DIRTY, SYNTHETIC_TRANSACTIONS, MERCHANTS,
    SCHEMA_V1, SCHEMA_V2, SCHEMA_V3,
    PIPELINE_V1_CODE, PIPELINE_V2_CODE, PROD_STACK_TRACE,
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sigma_platform.duckdb")

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"  Removed old database")

con = duckdb.connect(DB_PATH)
print("\n" + "=" * 55)
print("Day 9 — Sigma AI Ops Platform — DuckDB Setup")
print("=" * 55)

# ── Core tables ───────────────────────────────────────────────
print("\n[1/5] Creating core tables...")
con.execute("""
    CREATE TABLE bronze_transactions (
        transaction_id   VARCHAR,
        amount           DOUBLE,
        status           VARCHAR,
        merchant_id      VARCHAR,
        customer_id      VARCHAR,
        transaction_date VARCHAR,
        payment_method   VARCHAR
    )
""")
con.execute("""
    CREATE TABLE silver_transactions (
        transaction_id   VARCHAR PRIMARY KEY,
        amount           DOUBLE NOT NULL,
        status           VARCHAR NOT NULL,
        merchant_id      VARCHAR,
        customer_id      VARCHAR,
        transaction_date VARCHAR,
        payment_method   VARCHAR,
        merchant_name    VARCHAR,
        category         VARCHAR,
        city             VARCHAR,
        quality_flag     VARCHAR DEFAULT 'CLEAN'
    )
""")
con.execute("""
    CREATE TABLE gold_merchant_performance (
        merchant_id      VARCHAR,
        merchant_name    VARCHAR,
        category         VARCHAR,
        city             VARCHAR,
        total_revenue    DOUBLE,
        txn_count        INTEGER,
        failure_rate_pct DOUBLE
    )
""")
con.execute("""
    CREATE TABLE gold_daily_summary (
        report_date       VARCHAR,
        total_revenue     DOUBLE,
        total_txns        INTEGER,
        unique_customers  INTEGER,
        unique_merchants  INTEGER,
        failure_rate_pct  DOUBLE
    )
""")
con.execute("""
    CREATE TABLE merchants (
        merchant_id   VARCHAR PRIMARY KEY,
        merchant_name VARCHAR,
        category      VARCHAR,
        city          VARCHAR
    )
""")
print("  Core tables created")

# ── Bronze: all rows including dirty ─────────────────────────
print("\n[2/5] Loading Bronze + Merchants...")
for row in TRANSACTIONS_CLEAN + TRANSACTIONS_DIRTY:
    con.execute(
        "INSERT INTO bronze_transactions VALUES (?,?,?,?,?,?,?)",
        [row["transaction_id"], row["amount"], row["status"],
         row["merchant_id"], row["customer_id"], row["transaction_date"], row["payment_method"]]
    )
for m in MERCHANTS:
    con.execute("INSERT INTO merchants VALUES (?,?,?,?)",
                [m["merchant_id"], m["merchant_name"], m["category"], m["city"]])
print(f"  Bronze: {len(TRANSACTIONS_CLEAN + TRANSACTIONS_DIRTY)} rows | Merchants: {len(MERCHANTS)}")

# ── Silver: clean + enriched ──────────────────────────────────
print("\n[3/5] Loading Silver...")
merchant_map = {m["merchant_id"]: m for m in MERCHANTS}
seen = set()
silver_rows = []
for row in TRANSACTIONS_CLEAN:
    if not row["transaction_id"] or row["transaction_id"] in seen:
        continue
    seen.add(row["transaction_id"])
    m = merchant_map.get(row["merchant_id"], {})
    con.execute(
        "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [row["transaction_id"], row["amount"], row["status"], row["merchant_id"],
         row["customer_id"], row["transaction_date"], row["payment_method"],
         m.get("merchant_name"), m.get("category"), m.get("city"), "CLEAN"]
    )
    silver_rows.append(row)
print(f"  Silver: {len(silver_rows)} rows")

# ── Gold ──────────────────────────────────────────────────────
print("\n[4/5] Loading Gold...")
from collections import defaultdict
merch_agg = defaultdict(lambda: {"rev": 0.0, "total": 0, "failed": 0, "name": "", "cat": "", "city": ""})
date_agg  = defaultdict(lambda: {"rev": 0.0, "total": 0, "failed": 0, "cust": set(), "merch": set()})

for row in silver_rows:
    mid = row["merchant_id"]
    m = merchant_map.get(mid, {})
    merch_agg[mid]["name"] = m.get("merchant_name", "")
    merch_agg[mid]["cat"]  = m.get("category", "")
    merch_agg[mid]["city"] = m.get("city", "")
    merch_agg[mid]["total"] += 1
    if row["status"] == "COMPLETED": merch_agg[mid]["rev"] += row["amount"]
    if row["status"] == "FAILED":    merch_agg[mid]["failed"] += 1
    d = row["transaction_date"]
    date_agg[d]["total"] += 1
    date_agg[d]["cust"].add(row["customer_id"])
    date_agg[d]["merch"].add(mid)
    if row["status"] == "COMPLETED": date_agg[d]["rev"] += row["amount"]
    if row["status"] == "FAILED":    date_agg[d]["failed"] += 1

for mid, a in merch_agg.items():
    fr = round(a["failed"] / a["total"] * 100, 2) if a["total"] else 0
    con.execute("INSERT INTO gold_merchant_performance VALUES (?,?,?,?,?,?,?)",
                [mid, a["name"], a["cat"], a["city"], a["rev"], a["total"], fr])
for d, a in sorted(date_agg.items()):
    fr = round(a["failed"] / a["total"] * 100, 2) if a["total"] else 0
    con.execute("INSERT INTO gold_daily_summary VALUES (?,?,?,?,?,?)",
                [d, a["rev"], a["total"], len(a["cust"]), len(a["merch"]), fr])
print(f"  Gold merchant: {len(merch_agg)} rows | Gold daily: {len(date_agg)} rows")

# ── Team-specific tables ──────────────────────────────────────
print("\n[5/5] Creating team-specific tables...")

# Team 7: schema versions
con.execute(SCHEMA_V1); con.execute(SCHEMA_V2); con.execute(SCHEMA_V3)
for row in TRANSACTIONS_CLEAN[:8]:
    con.execute("INSERT INTO txn_v1 VALUES (?,?,?,?,?)",
                [row["transaction_id"], row["amount"], row["status"],
                 row["merchant_id"], row["transaction_date"]])
    con.execute("INSERT INTO txn_v2 VALUES (?,?,?,?,?,?,?)",
                [row["transaction_id"], row["amount"], row["status"],
                 row["merchant_id"], row["customer_id"], row["transaction_date"], row["payment_method"]])
    con.execute("INSERT INTO txn_v3 VALUES (?,?,?,?,?,?)",
                [row["transaction_id"], row["amount"], row["status"],
                 row["merchant_id"], row["customer_id"], row["transaction_date"]])

# Team 8: synthetic data
con.execute("""
    CREATE TABLE synthetic_transactions (
        transaction_id   VARCHAR,
        amount           DOUBLE,
        status           VARCHAR,
        merchant_id      VARCHAR,
        customer_id      VARCHAR,
        transaction_date VARCHAR,
        payment_method   VARCHAR
    )
""")
for row in SYNTHETIC_TRANSACTIONS:
    con.execute("INSERT INTO synthetic_transactions VALUES (?,?,?,?,?,?,?)",
                [row["transaction_id"], row["amount"], row["status"],
                 row["merchant_id"], row["customer_id"], row["transaction_date"], row["payment_method"]])

# Store pipeline code + stack trace as metadata table (Teams 3 & 6)
con.execute("""
    CREATE TABLE pipeline_versions (
        version VARCHAR PRIMARY KEY,
        code    VARCHAR
    )
""")
con.execute("INSERT INTO pipeline_versions VALUES (?,?)", ["v1", PIPELINE_V1_CODE])
con.execute("INSERT INTO pipeline_versions VALUES (?,?)", ["v2", PIPELINE_V2_CODE])
con.execute("INSERT INTO pipeline_versions VALUES (?,?)", ["stack_trace", PROD_STACK_TRACE])

print("  Schema versions (txn_v1/v2/v3), synthetic_transactions, pipeline_versions created")

# ── Summary ───────────────────────────────────────────────────
print("\n── Row counts ────────────────────────────────────────")
for t in ["bronze_transactions", "silver_transactions",
          "gold_merchant_performance", "gold_daily_summary",
          "synthetic_transactions", "txn_v1", "txn_v2", "txn_v3"]:
    n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t:<35} {n:>3} rows")

con.close()
print(f"\n  sigma_platform.duckdb ready at {DB_PATH}\n")
