import duckdb
import os

DB_PATH = "soda_training.duckdb"

def setup():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    con = duckdb.connect(DB_PATH)
    
    # ── DAY 1: Clean Data (The Baseline) ──
    con.execute("""
        CREATE TABLE day1_orders (
            order_id VARCHAR,
            customer_id VARCHAR,
            amount DOUBLE,
            status VARCHAR
        )
    """)
    
    day1_data = [
        ('ORD-001', 'CUST-100', 150.00, 'COMPLETED'),
        ('ORD-002', 'CUST-101', 89.50, 'PENDING'),
        ('ORD-003', 'CUST-102', 210.00, 'COMPLETED'),
        ('ORD-004', 'CUST-103', 15.20, 'FAILED'),
        ('ORD-005', 'CUST-104', 500.00, 'COMPLETED')
    ]
    
    con.executemany("INSERT INTO day1_orders VALUES (?, ?, ?, ?)", day1_data)
    print(f"Created day1_orders with {len(day1_data)} clean rows.")

    # ── DAY 2: The Poison Pill (Silent Failures) ──
    con.execute("""
        CREATE TABLE day2_orders (
            order_id VARCHAR,
            customer_id VARCHAR,
            amount DOUBLE,
            status VARCHAR
        )
    """)
    
    day2_data = [
        ('ORD-006', 'CUST-105', 120.00, 'COMPLETED'),
        ('ORD-007', 'CUST-106', -50.00, 'COMPLETED'),    # BUG: Negative amount (refund formatted wrong)
        ('ORD-008', 'CUST-107', 300.00, 'UNKNOWN'),      # BUG: Invalid status introduced by upstream
        ('ORD-009', None,       45.00, 'PENDING'),       # BUG: Missing customer ID
        ('ORD-006', 'CUST-105', 120.00, 'COMPLETED')     # BUG: Exact duplicate of ORD-006
    ]
    
    con.executemany("INSERT INTO day2_orders VALUES (?, ?, ?, ?)", day2_data)
    print(f"Created day2_orders with {len(day2_data)} dirty rows.")
    
    con.close()
    print(f"\nDatabase ready: {DB_PATH}")

if __name__ == "__main__":
    setup()
