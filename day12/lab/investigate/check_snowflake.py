"""
Phase 2 Investigation Tool — Snowflake
Shows hourly row counts and GMV for the last 12 hours.
The gap should be visible here if data stopped loading.
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()

try:
    import snowflake.connector
except ImportError:
    print("pip install snowflake-connector-python"); sys.exit(1)

conn = snowflake.connector.connect(
    account=os.getenv("SNOWFLAKE_ACCOUNT"),
    user=os.getenv("SNOWFLAKE_USER"),
    password=os.getenv("SNOWFLAKE_PASSWORD"),
    database=os.getenv("SNOWFLAKE_DATABASE", "SIGMA"),
    schema=os.getenv("SNOWFLAKE_SCHEMA", "SILVER"),
    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH"),
)

print("\nSNOWFLAKE — Hourly row count and GMV (last 12 hours)")
print("=" * 65)

cur = conn.cursor()
cur.execute("""
    SELECT
        TO_CHAR(DATE_TRUNC('hour', _loaded_at), 'YYYY-MM-DD HH24:MI') AS hour_utc,
        COUNT(*)         AS tx_count,
        SUM(amount)      AS gmv_inr,
        MIN(_loaded_at)  AS first_loaded,
        MAX(_loaded_at)  AS last_loaded
    FROM SIGMA.SILVER.TRANSACTIONS
    WHERE _loaded_at >= DATEADD(hour, -12, CURRENT_TIMESTAMP())
    GROUP BY 1
    ORDER BY 1
""")

rows = cur.fetchall()
if not rows:
    print("\n  NO DATA in last 12 hours. This is the problem.\n")
else:
    print(f"\n  {'Hour (UTC)':<20} {'Transactions':>14} {'GMV (INR)':>16}")
    print("  " + "-" * 52)
    total_tx  = 0
    total_gmv = 0.0
    for row in rows:
        hour, tx, gmv = row[0], row[1], float(row[2] or 0)
        total_tx  += tx
        total_gmv += gmv
        flag = "  ← GAP" if tx == 0 else ""
        print(f"  {hour:<20} {tx:>14,} {gmv:>16,.2f}{flag}")
    print("  " + "-" * 52)
    print(f"  {'TOTAL':<20} {total_tx:>14,} {total_gmv:>16,.2f}")

print()

# Show the most recent 3 records loaded
cur.execute("""
    SELECT transaction_id, merchant_name, amount, transaction_date, _loaded_at
    FROM SIGMA.SILVER.TRANSACTIONS
    ORDER BY _loaded_at DESC
    LIMIT 3
""")
recent = cur.fetchall()
if recent:
    print(f"  Most recent 3 records in Snowflake:")
    for r in recent:
        print(f"    {r[0]}  {r[1]:<15}  ₹{float(r[2]):>10,.2f}  loaded: {r[4]}")

conn.close()
print()
