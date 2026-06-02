"""
challenge_pipeline.py — Sigma DataTech Bronze→Silver loader (new hire PR)

Loads raw transaction CSV from S3, applies Silver-layer quality rules,
and writes results to DuckDB. Submitted for code review — not yet merged.
"""

import os
import json
import logging
from datetime import date
# NOTE: datetime.datetime is used in apply_silver_rules but NOT imported — NameError at runtime
import requests  # BUG 1: imported but not in requirements.txt — ImportError in CI

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────────────
S3_BUCKET   = os.getenv("SIGMA_S3_BUCKET", "sigma-datatech-raw")
S3_PREFIX   = os.getenv("SIGMA_S3_PREFIX", "transactions/")
DB_PATH     = os.getenv("SIGMA_DB_PATH", "sigma_platform.duckdb")
CUTOFF_DATE = date(2024, 1, 15)


# ── Data loading ──────────────────────────────────────────────────────────────

def fetch_transactions_from_db(con) -> list:
    """Fetch raw transactions from DuckDB bronze table."""
    rows = con.execute("SELECT * FROM bronze_transactions").fetchall()
    cols = [d[0] for d in con.description]
    return [dict(zip(cols, row)) for row in rows]


def filter_recent_transactions(transactions: list, cutoff: date) -> list:
    """Return transactions on or after the cutoff date.

    BUG 2 (off-by-one): uses >= instead of > so the cutoff date itself
    is included, causing one extra day of data to be processed every run.
    The business rule is: load data AFTER the cutoff, not including it.
    """
    result = []
    for txn in transactions:
        txn_date = txn.get("transaction_date")
        if isinstance(txn_date, str):
            txn_date = date.fromisoformat(txn_date)
        if txn_date >= cutoff:  # should be: txn_date > cutoff
            result.append(txn)
    return result


# ── Transformation ────────────────────────────────────────────────────────────

def apply_silver_rules(transactions: list, merchants: list) -> list:
    """Apply Silver-layer quality rules: deduplicate, filter nulls, enrich."""
    merchant_map = {m["merchant_id"]: m for m in merchants}
    pipeline_run_id = "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")  # BUG 3: datetime not imported

    seen_ids = set()
    silver = []
    for txn in transactions:
        if txn.get("transaction_id") is None:
            continue
        if txn.get("amount", 0) < 0:
            continue
        if txn["transaction_id"] in seen_ids:
            continue
        seen_ids.add(txn["transaction_id"])

        merchant = merchant_map.get(txn.get("merchant_id"), {})
        row = {
            **txn,
            "merchant_name": merchant.get("merchant_name"),
            "category":      merchant.get("category"),
            "city":          merchant.get("city"),
            "quality_flag":  "CLEAN" if txn.get("merchant_id") in merchant_map else "UNMATCHED",
            "pipeline_run":  pipeline_run_id,
        }
        silver.append(row)
    return silver


# ── Loading ───────────────────────────────────────────────────────────────────

def load_to_silver(con, silver_rows: list) -> int:
    """Insert Silver rows into DuckDB. Returns row count loaded."""
    loaded = 0
    for row in silver_rows:
        try:
            con.execute(
                """INSERT OR IGNORE INTO silver_transactions
                   (transaction_id, amount, status, merchant_id, customer_id,
                    transaction_date, payment_method, merchant_name, category, city, quality_flag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    row["transaction_id"], row["amount"], row["status"],
                    row.get("merchant_id"), row.get("customer_id"),
                    row.get("transaction_date"), row.get("payment_method"),
                    row.get("merchant_name"), row.get("category"),
                    row.get("city"), row.get("quality_flag"),
                ],
            )
            loaded += 1
        except Exception as e:
            # BUG 4: swallows the exception — logs it but returns empty silently.
            # Caller has no idea rows were skipped; data loss is invisible.
            logger.error("Failed to insert %s: %s", row.get("transaction_id"), e)

    return loaded


# ── Pipeline entry point ──────────────────────────────────────────────────────

def run_pipeline(con, merchants: list) -> dict:
    """Run Bronze→Silver load pipeline. Returns summary dict."""
    transactions = fetch_transactions_from_db(con)
    recent       = filter_recent_transactions(transactions, CUTOFF_DATE)
    silver_rows  = apply_silver_rules(recent, merchants)
    loaded       = load_to_silver(con, silver_rows)

    return {
        "fetched": len(transactions),
        "after_filter": len(recent),
        "silver_rows": len(silver_rows),
        "loaded": loaded,
    }
