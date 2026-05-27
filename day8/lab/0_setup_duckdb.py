"""
Day 8 — DuckDB Setup Script
Run this ONCE before any other Day 8 script.
Creates sigma_platform.duckdb with Bronze / Silver / Gold tables.

Usage: python 0_setup_duckdb.py   (from repo/day8/lab/)
"""

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import duckdb
from sample_data import (
    TRANSACTIONS_CLEAN,
    TRANSACTIONS_DIRTY,
    MERCHANTS,
    DUCKDB_SCHEMA,
    transform_bronze_to_silver,
    compute_merchant_performance,
    compute_daily_summary,
)

LAB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(LAB_DIR, "sigma_platform.duckdb")

# Remove stale DB so setup is idempotent
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"  Removed old {DB_PATH}")

con = duckdb.connect(DB_PATH)

print("\n" + "=" * 50)
print("Day 8 DuckDB Setup — Sigma Intelligence Platform")
print("=" * 50)

# ── Create tables ────────────────────────────────────
print("\n[1/4] Creating tables...")
for table_name, ddl in DUCKDB_SCHEMA.items():
    con.execute(ddl)
    print(f"  Created: {table_name}")

# ── Bronze: all rows (clean + dirty) ────────────────
print("\n[2/4] Loading Bronze layer (clean + dirty rows)...")
all_txns = TRANSACTIONS_CLEAN + TRANSACTIONS_DIRTY
for row in all_txns:
    con.execute(
        "INSERT INTO bronze_transactions "
        "(transaction_id, amount, status, merchant_id, customer_id, transaction_date, payment_method) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [row["transaction_id"], row["amount"], row["status"],
         row["merchant_id"], row["customer_id"], row["transaction_date"],
         row["payment_method"]],
    )
print(f"  Inserted {len(all_txns)} rows into bronze_transactions")

# ── Merchants ────────────────────────────────────────
for m in MERCHANTS:
    con.execute(
        "INSERT INTO merchants VALUES (?, ?, ?, ?)",
        [m["merchant_id"], m["merchant_name"], m["category"], m["city"]],
    )
print(f"  Inserted {len(MERCHANTS)} rows into merchants")

# ── Silver: clean rows only ──────────────────────────
print("\n[3/4] Loading Silver layer (clean rows, enriched)...")
silver_rows = transform_bronze_to_silver(TRANSACTIONS_CLEAN, MERCHANTS)
for row in silver_rows:
    con.execute(
        "INSERT INTO silver_transactions "
        "(transaction_id, amount, status, merchant_id, customer_id, "
        "transaction_date, payment_method, merchant_name, category, city, quality_flag) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [row["transaction_id"], row["amount"], row["status"],
         row["merchant_id"], row["customer_id"], row["transaction_date"],
         row["payment_method"], row["merchant_name"], row["category"],
         row["city"], row["quality_flag"]],
    )
print(f"  Inserted {len(silver_rows)} rows into silver_transactions")

# ── Gold ─────────────────────────────────────────────
print("\n[4/4] Loading Gold layer (aggregates)...")
from datetime import date
report_date = date(2024, 1, 31)

merchant_perf = compute_merchant_performance(silver_rows)
for row in merchant_perf:
    con.execute(
        "INSERT INTO gold_merchant_performance VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [row["merchant_id"], row["merchant_name"], row["category"], row["city"],
         report_date, row["total_revenue"], row["txn_count"], row["failure_rate_pct"]],
    )
print(f"  Inserted {len(merchant_perf)} rows into gold_merchant_performance")

daily = compute_daily_summary(silver_rows)
for row in daily:
    con.execute(
        "INSERT INTO gold_daily_summary VALUES (?, ?, ?, ?, ?, ?)",
        [row["report_date"], row["total_revenue"], row["total_txns"],
         row["unique_customers"], row["unique_merchants"], row["failure_rate_pct"]],
    )
print(f"  Inserted {len(daily)} rows into gold_daily_summary")

# ── Verify ───────────────────────────────────────────
print("\n── Table row counts ──────────────────────────────")
for table in ["bronze_transactions", "merchants", "silver_transactions",
              "gold_merchant_performance", "gold_daily_summary"]:
    count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table:<35} {count:>3} rows")

con.close()

print(f"\n  sigma_platform.duckdb created at:")
print(f"  {DB_PATH}")
print("\n  Ready. Run the sprint scripts in order:")
print("    python 1_code_review.py")
print("    python 2_doc_generator.py")
print("    python 3_testing_sprint.py")
print("    python 4_ci_slo.py")
print("    python 5_observability.py")
print("    python 6_competitive_build.py\n")
