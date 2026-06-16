# Patched by Self-Healing Agent — 2026-05-29T17:34:27.648283
# Attempts needed: 3

import duckdb, os

DB_PATH = r"/Users/as-mac-1317/Desktop/genai2/day_6/sigma-genai-de/day10/lab/sigma_platform.duckdb"

def run_merchant_report():
    conn = duckdb.connect(DB_PATH)
    if conn.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='silver_transactions'").fetchone()[0] == 0:
        print("Table silver_transactions does not exist.")
        return
    df = conn.execute("SELECT * FROM silver_transactions WHERE amount > 0").fetchdf()
    if df.empty:
        print("No data found.")
        return
    total = df["amount"].sum()
    df2 = df.groupby("merchant_id").agg({"amount": "mean"}).reset_index()
    df2.columns = ["merchant_id", "avg_amount"]
    df2_sorted = df2.sort_values("avg_amount", ascending=False)
    conn.close()
    print(f"Done. Total: {total:.2f}, Merchants: {len(df2)}")
    top = df2_sorted.iloc[0]["merchant_id"]
    print(f"Top merchant by avg amount: {top}")

if __name__ == "__main__":
    run_merchant_report()