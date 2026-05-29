"""
==============================================================================
DAY 10 — LAB 2 STUDENT BUILD TASK
Build a 2-node LangGraph from scratch
==============================================================================

You just ran a 3-node LangGraph in 2_langgraph_sql_agent.py.
Now you build a smaller one yourself.

THE GRAPH:
  Every NL2SQL system needs a safety layer.
  A "SELECT *" on a 4M-row table kills the warehouse.
  You are building that safety layer.

  Input SQL
      ↓
  sql_checker_node   → checks if SQL has a WHERE clause (no LLM needed)
      ↓
  (safe?)   → safe_executor_node  → runs the SQL  → result
  (unsafe?) → safe_executor_node  → "BLOCKED: ..." → result

RULES:
  - Do NOT copy code from 2_langgraph_sql_agent.py
  - Fill in every  pass  below with your own code
  - Run this file: python 2b_student_build.py
  - Both test cases must pass before you show the trainer

SUCCESS CRITERION:
  ✅ SAFE test   → prints actual data rows from DuckDB
  ❌ UNSAFE test → prints "BLOCKED: No WHERE clause..."
==============================================================================
"""

import os, duckdb
from typing import TypedDict
from langgraph.graph import StateGraph, END

DB_PATH = os.path.join(os.path.dirname(__file__), "sigma_platform.duckdb")


# ── STEP 1: Define the shared state ───────────────────────────────────────────
# Every node reads from and writes to this TypedDict.
# Nothing moves between nodes except through this state object.

class CheckerState(TypedDict):
    sql          : str    # the SQL query to check
    is_safe      : bool   # True if the SQL has a WHERE clause
    check_reason : str    # one sentence: why it is safe or not
    result       : str    # query result (if safe) or blocked message (if not)


# ── STEP 2: sql_checker_node ──────────────────────────────────────────────────
# No LLM. No Bedrock. Pure Python logic.
# Check if "WHERE" appears anywhere in the SQL (case-insensitive).
# Return ONLY the fields you are setting — LangGraph merges the rest.

def sql_checker_node(state: CheckerState) -> dict:
    """
    Check the SQL for a WHERE clause.
    Return: {"is_safe": bool, "check_reason": str}
    ~4 lines of code.
    """
    pass  # ← YOUR CODE HERE


# ── STEP 3: safe_executor_node ────────────────────────────────────────────────
# This node handles BOTH the safe and blocked paths.
# If safe: run the SQL against DuckDB and return the result.
# If not:  return a blocked message — do NOT run the SQL.

def safe_executor_node(state: CheckerState) -> dict:
    """
    If state["is_safe"]:
        connect to DuckDB (read_only=True), run state["sql"], return result as string
    If not state["is_safe"]:
        return {"result": "BLOCKED: " + state["check_reason"]}
    ~10 lines of code.
    """
    pass  # ← YOUR CODE HERE


# ── STEP 4: Routing function ──────────────────────────────────────────────────
# This is NOT a node — it is the decision function for add_conditional_edges.
# LangGraph calls this AFTER sql_checker_node runs.
# The string you return must match a key in the routing dict (Step 5).

def route_by_safety(state: CheckerState) -> str:
    """
    Return "execute" if state["is_safe"] is True.
    Return "blocked" if state["is_safe"] is False.
    1 line of code.
    """
    pass  # ← YOUR CODE HERE


# ── STEP 5: Build and wire the graph ─────────────────────────────────────────
# This is where you assemble the graph.
# Pattern — refer to build_graph() in 2_langgraph_sql_agent.py if stuck on syntax.
# Do NOT copy it — understand each line, then write your own.

def build_checker_graph():
    g = StateGraph(CheckerState)

    # Add nodes
    # g.add_node("check",   ???)
    # g.add_node("execute", ???)   # safe path
    # g.add_node("blocked", ???)   # unsafe path (same function, different node name)
    pass  # ← replace this pass and uncomment the add_node lines

    # Set the entry point (first node to run)
    # g.set_entry_point("???")
    pass  # ← uncomment and complete

    # Add conditional edges FROM "check" node
    # After sql_checker_node runs, LangGraph calls route_by_safety(state)
    # and follows the edge whose key matches the returned string.
    # g.add_conditional_edges(
    #     "check",
    #     route_by_safety,
    #     {"execute": "execute", "blocked": "blocked"}
    # )
    pass  # ← uncomment and complete

    # Both paths end at END
    # g.add_edge("execute", END)
    # g.add_edge("blocked", END)
    pass  # ← uncomment and complete

    return g.compile()


# ── STEP 6: Run the tests ─────────────────────────────────────────────────────
# Do not modify this block. Just make Steps 1–5 work and this will pass.

if __name__ == "__main__":
    print("\n" + "="*70)
    print("LAB 2 STUDENT BUILD — SQL Safety Graph")
    print("="*70)

    app = build_checker_graph()

    safe_sql   = "SELECT merchant_id, COUNT(*) AS txn_count FROM silver_transactions WHERE amount > 100 GROUP BY 1 ORDER BY 2 DESC LIMIT 5"
    unsafe_sql = "SELECT * FROM silver_transactions"

    for label, sql in [("✅ SAFE SQL (has WHERE)", safe_sql),
                       ("❌ UNSAFE SQL (no WHERE)", unsafe_sql)]:
        print(f"\n── {label} ──────────────────────────────────────────────")
        print(f"  SQL: {sql[:80]}...")
        init  = {"sql": sql, "is_safe": False, "check_reason": "", "result": ""}
        final = app.invoke(init)
        print(f"  is_safe      : {final['is_safe']}")
        print(f"  check_reason : {final['check_reason']}")
        print(f"  result       : {final['result'][:150]}")

    print("\n" + "─"*60)
    print("DEBRIEF — answer both before Lab 3:")
    print("─"*60)
    q1 = input('1. add_conditional_edges takes a dict {"execute": "execute", "blocked": "blocked"}.\n   What does this dict do? Why is it needed? ').strip()
    q2 = input('2. Both paths use the same function (safe_executor_node) but different node names.\n   Why not just one node for both paths? ').strip()

    print("\n✅ Build task complete. Show the trainer this output before Lab 3.")
    print(f"\nYour answers:")
    print(f"  Q1: {q1 or 'NOT ANSWERED'}")
    print(f"  Q2: {q2 or 'NOT ANSWERED'}")
