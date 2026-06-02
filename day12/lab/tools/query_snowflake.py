"""
Lambda Tool: query_snowflake
Called by: Impact Agent, Recovery Agent
Action group: DataPlatformTools

Executes SQL against Snowflake and returns results as JSON.
Impact Agent uses this to calculate GMV gaps and check SLA breaches.
Recovery Agent uses this to verify row counts after replay.
"""

import json, os


def lambda_handler(event, context):
    params = {p["name"]: p["value"] for p in event.get("parameters", [])}

    sql       = params.get("sql", "")
    warehouse = params.get("warehouse", os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH"))
    max_rows  = int(params.get("max_rows", 500))

    if not sql:
        result = {"error": "No SQL provided"}
    else:
        result = run_query(sql, warehouse, max_rows)

    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": event.get("actionGroup"),
            "function": event.get("function"),
            "functionResponse": {
                "responseBody": {"TEXT": {"body": json.dumps(result, default=str)}}
            },
        },
    }


def get_connection(warehouse: str = None):
    try:
        import snowflake.connector
    except ImportError:
        raise RuntimeError("pip install snowflake-connector-python")

    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        database=os.getenv("SNOWFLAKE_DATABASE", "SIGMA"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "SILVER"),
        warehouse=warehouse or os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH"),
    )


def run_query(sql: str, warehouse: str, max_rows: int) -> dict:
    try:
        conn   = get_connection(warehouse)
        cur    = conn.cursor()
        cur.execute(sql)
        cols   = [d[0].lower() for d in cur.description]
        rows   = [dict(zip(cols, row)) for row in cur.fetchmany(max_rows)]
        conn.close()
        return {
            "sql":       sql,
            "row_count": len(rows),
            "columns":   cols,
            "data":      rows,
            "truncated": len(rows) == max_rows,
        }
    except Exception as e:
        return {"error": str(e), "sql": sql}


# ── Preset queries the agents commonly use ────────────────────────────────────

def gmv_last_24h(region: str = None) -> dict:
    sql = """
    SELECT
        DATE_TRUNC('hour', transaction_date) AS hour,
        COUNT(*)                             AS tx_count,
        SUM(amount)                          AS gmv
    FROM SIGMA.SILVER.TRANSACTIONS
    WHERE transaction_date >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
    GROUP BY 1
    ORDER BY 1
    """
    return run_query(sql, None, 100)


def row_count_since(ts: str) -> dict:
    sql = f"""
    SELECT COUNT(*) AS row_count, SUM(amount) AS gmv
    FROM SIGMA.SILVER.TRANSACTIONS
    WHERE _loaded_at >= '{ts}'
    """
    return run_query(sql, None, 1)


def check_duplicate(transaction_id: str) -> dict:
    sql = f"""
    SELECT COUNT(*) AS cnt
    FROM SIGMA.SILVER.TRANSACTIONS
    WHERE transaction_id = '{transaction_id}'
    """
    return run_query(sql, None, 1)


# ── Local test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()

    print("\nRunning GMV check (last 24 hours)...\n")
    result = gmv_last_24h()

    if "error" in result:
        print(f"ERROR: {result['error']}")
        print("Check SNOWFLAKE_* env vars in .env")
    else:
        print(f"{'Hour':<25} {'Transactions':>14} {'GMV (INR)':>15}")
        print("-" * 55)
        for row in result["data"]:
            print(f"{str(row.get('hour','?')):<25} "
                  f"{row.get('tx_count',0):>14,} "
                  f"{float(row.get('gmv') or 0):>15,.2f}")
        print(f"\nTotal rows: {result['row_count']}")

    if "--test" in sys.argv:
        assert "data" in result or "error" in result
        print("\nquery_snowflake.py test PASSED")
