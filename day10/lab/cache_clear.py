"""
cache_clear.py — Reset the self-healing agent's SQLite memory.

Run this whenever you want to start fresh:
  - After pulling a new version of Lab 4
  - If the cache is behaving unexpectedly
  - Before a demo or assessment

Usage:
  python cache_clear.py
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "agent_memory.db")

if not os.path.exists(DB_PATH):
    print(f"No cache found at {DB_PATH} — nothing to clear.")
else:
    conn = sqlite3.connect(DB_PATH)
    rows_before = conn.execute("SELECT COUNT(*) FROM healing_history").fetchone()[0]
    conn.execute("DELETE FROM healing_history")
    conn.commit()
    conn.close()
    print(f"Cache cleared. {rows_before} record(s) removed from {DB_PATH}")
    print("You're starting fresh. Run Lab 4 now.")
