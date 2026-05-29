"""
==============================================================================
DAY 10 — LAB 2: TWO-AGENT LANGGRAPH SQL WORKFLOW WITH MEMORY
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech's analytics lead is tired of writing SQL. She wants to ask
questions in plain English and get answers from the Gold layer instantly.

But there's a catch: junior engineers using raw NL2SQL ship wrong queries.
The CFO caught one last week — a query that double-counted refunds.

Your solution: a 2-agent pipeline where Agent 1 generates SQL and Agent 2
independently reviews and optimises it BEFORE execution. If Agent 2 rejects
the SQL, it sends it back with feedback. Agent 1 must fix it and resubmit.

Only approved SQL runs. Every decision is logged. Every query remembered.

WHAT YOU WILL LEARN
-------------------
- LangGraph StateGraph: nodes, edges, conditional routing
- TypedDict state shared across agents
- SQLite-backed agent memory: agents remember past queries across runs
- Why multi-agent review catches bugs single agents miss
- The difference between a chain (Lab 1) and a stateful graph (this lab)

MANUAL FIRST (3 minutes)
-------------------------
Read this NL question: "Which payment methods are growing fastest this month?"
Write the SQL you would generate. Then write 3 things that could be wrong with
your SQL (wrong date filter, missing NULL handling, wrong aggregation...).
THAT is what Agent 2 is checking for.

THE FULL LOOP
-------------
NL Question
    ↓
Agent 1 (SQL Generator — Nova Pro)
    ↓
Agent 2 (SQL Reviewer — Nova Pro)
    ↓ [REJECTED — feedback]
Agent 1 (fixes SQL, max 3 rounds)
    ↓ [APPROVED]
Executor (runs SQL against DuckDB)
    ↓
Final Answer + Memory saved to SQLite

WE USE DUCKDB BUT IF YOU WANT TO USE SNOWFLAKE CONNECTION (Just 1-line swap)

**The Snowflake Swap (The Stretch Assignment for Super Fast Finishers)**

-------------------------------------------------------
# Replace DuckDB executor with:
import snowflake.connector
conn = snowflake.connector.connect(
    account=os.environ["SF_ACCOUNT"], user=os.environ["SF_USER"],
    password=os.environ["SF_PASSWORD"], database="SIGMA_PROD",
    schema="GOLD", warehouse="COMPUTE_WH"
)
result = conn.cursor().execute(approved_sql).fetchdf()
# Everything else stays identical. The agents don't know or care.

==============================================================================
OUTPUT
------
  agent_outputs/langgraph_trace.json  — full state at each node
  agent_outputs/approved_queries.json — all approved SQL + results
  agent_memory.db                     — SQLite memory (persists across runs!)
==============================================================================
"""

import os, sys, json, sqlite3, duckdb
from datetime import datetime
from typing import TypedDict, List, Optional

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
    from langgraph.graph import StateGraph, END
except ImportError as e:
    print(f"[ERROR] Missing dependency: {e}")
    print("Run: pip install langgraph boto3 duckdb")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_PRO  = "amazon.nova-pro-v1:0"
REGION     = "us-east-1"
DB_PATH    = os.path.join(os.path.dirname(__file__), "sigma_platform.duckdb")
MEM_PATH   = os.path.join(os.path.dirname(__file__), "agent_memory.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
MAX_REVIEW_ROUNDS = 3
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "", model: str = MODEL_PRO) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 2000, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=model, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]

# ── SQLite Agent Memory ───────────────────────────────────────────────────────
class AgentMemory:
    """Persists past queries and results across runs. Agents consult this
    before generating new SQL — they don't repeat past mistakes."""

    def __init__(self, db_path: str = MEM_PATH):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT,
                final_sql TEXT,
                result_summary TEXT,
                review_rounds INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS review_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sql_query TEXT,
                feedback TEXT,
                was_rejected INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def save_query(self, question: str, sql: str, result_summary: str, rounds: int):
        self.conn.execute(
            "INSERT INTO query_history (question, final_sql, result_summary, review_rounds) VALUES (?,?,?,?)",
            (question, sql, result_summary[:500], rounds)
        )
        self.conn.commit()

    def save_feedback(self, sql: str, feedback: str, rejected: bool):
        self.conn.execute(
            "INSERT INTO review_feedback (sql_query, feedback, was_rejected) VALUES (?,?,?)",
            (sql, feedback, 1 if rejected else 0)
        )
        self.conn.commit()

    def get_relevant_context(self, question: str, limit: int = 3) -> str:
        rows = self.conn.execute(
            """SELECT question, final_sql, result_summary, review_rounds
               FROM query_history ORDER BY id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        if not rows:
            return "No previous queries in memory."
        parts = []
        for q, sql, summary, rounds in rows:
            parts.append(f"Past Q: {q}\nSQL used: {sql}\nResult: {summary}\nReview rounds: {rounds}")
        return "\n---\n".join(parts)

    def get_schema(self) -> str:
        try:
            conn = duckdb.connect(DB_PATH, read_only=True)
            tables = conn.execute("SHOW TABLES").fetchall()
            parts = []
            for (t,) in tables:
                cols = conn.execute(f"DESCRIBE {t}").fetchall()
                col_str = ", ".join(f"{c[0]}:{c[1]}" for c in cols)
                parts.append(f"{t}({col_str})")
            conn.close()
            return " | ".join(parts)
        except Exception as e:
            return f"Schema error: {e}"

memory = AgentMemory()

# ── LangGraph State ───────────────────────────────────────────────────────────
class SQLAgentState(TypedDict):
    question:        str
    memory_context:  str
    db_schema:       str
    sql_query:       str
    review_feedback: str
    review_rounds:   int
    approved:        bool
    execution_result: str
    final_answer:    str
    reasoning_trace: List[str]
    error:           Optional[str]

# ── Node 1: SQL Generator ─────────────────────────────────────────────────────
def sql_generator_node(state: SQLAgentState) -> dict:
    print(f"\n[Agent 1 — SQL Generator] Round {state['review_rounds'] + 1}")

    feedback_section = ""
    if state["review_feedback"]:
        feedback_section = f"""
REVIEWER FEEDBACK FROM LAST ATTEMPT (fix these issues):
{state['review_feedback']}
"""

    prompt = f"""You are a SQL expert for Sigma DataTech.
Generate a single, production-ready SQL query to answer this question.

DATABASE SCHEMA:
{state['db_schema']}

MEMORY — PAST QUERIES (learn from these, avoid repeating mistakes):
{state['memory_context']}
{feedback_section}
QUESTION: {state['question']}

Rules:
- Write SQL compatible with DuckDB
- Handle NULL values explicitly
- Use appropriate date functions for DuckDB
- Do NOT use CTEs unless necessary — prefer subqueries
- Return ONLY the SQL query, nothing else. No explanation. No markdown fences.
"""

    sql = call_bedrock(prompt).strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()

    trace_entry = f"[Generator] Round {state['review_rounds']+1}: Generated SQL ({len(sql)} chars)"
    print(f"  SQL: {sql[:150]}...")

    return {
        "sql_query": sql,
        "reasoning_trace": state["reasoning_trace"] + [trace_entry],
        "approved": False,
    }

# ── Node 2: SQL Reviewer ──────────────────────────────────────────────────────
def sql_reviewer_node(state: SQLAgentState) -> dict:
    print(f"\n[Agent 2 — SQL Reviewer] Reviewing...")

    prompt = f"""You are a senior data engineer reviewing SQL before it runs in production.
Review this SQL query critically.

DATABASE SCHEMA:
{state['db_schema']}

QUESTION BEING ANSWERED: {state['question']}

SQL TO REVIEW:
{state['sql_query']}

Check for ALL of these:
1. Correctness — does the SQL actually answer the question?
2. NULL handling — are nulls handled or could they silently drop rows?
3. Date/time logic — are date filters correct for DuckDB syntax?
4. Aggregation logic — are GROUP BY, HAVING, window functions correct?
5. Performance — would this scan the full table unnecessarily on 4M rows?
6. Double-counting — any risk of row duplication from joins?

Respond in EXACTLY this format:
VERDICT: APPROVED or REJECTED
ISSUES: (list each issue numbered, or "None" if approved)
SPECIFIC_FIX: (exactly what to change in the SQL, or "None" if approved)
"""

    review_text = call_bedrock(prompt)
    approved    = "VERDICT: APPROVED" in review_text.upper() or "APPROVED" in review_text[:50].upper()
    feedback    = ""

    if not approved:
        issues_match = review_text.split("ISSUES:")[-1].split("SPECIFIC_FIX:")[0].strip() if "ISSUES:" in review_text else review_text
        fix_match    = review_text.split("SPECIFIC_FIX:")[-1].strip() if "SPECIFIC_FIX:" in review_text else ""
        feedback     = f"ISSUES:\n{issues_match}\n\nSPECIFIC FIX REQUIRED:\n{fix_match}"
        memory.save_feedback(state["sql_query"], feedback, rejected=True)
        print(f"  ❌ REJECTED — {issues_match[:100]}")
    else:
        memory.save_feedback(state["sql_query"], "Approved", rejected=False)
        print(f"  ✅ APPROVED")

    trace_entry = f"[Reviewer] Round {state['review_rounds']+1}: {'APPROVED' if approved else 'REJECTED'}"

    return {
        "approved":        approved,
        "review_feedback": feedback if not approved else "",
        "review_rounds":   state["review_rounds"] + 1,
        "reasoning_trace": state["reasoning_trace"] + [trace_entry],
    }

# ── Node 3: SQL Executor ──────────────────────────────────────────────────────
def sql_executor_node(state: SQLAgentState) -> dict:
    print(f"\n[Executor] Running approved SQL against DuckDB...")
    # ── SNOWFLAKE SWAP POINT ──────────────────────────────────────────────────
    # Uncomment these 4 lines and remove the DuckDB block below to use Snowflake:
    # conn = snowflake.connector.connect(account=os.environ["SF_ACCOUNT"], ...)
    # df = conn.cursor().execute(state["sql_query"]).fetch_pandas_all()
    # result_str = df.to_string(index=False, max_rows=30)
    # ─────────────────────────────────────────────────────────────────────────
    try:
        conn   = duckdb.connect(DB_PATH, read_only=True)
        df     = conn.execute(state["sql_query"]).fetchdf()
        conn.close()
        result_str = df.to_string(index=False, max_rows=30) if not df.empty else "Query returned 0 rows."
        print(f"  Result: {len(df)} rows returned")
        print(f"\n{result_str}\n")
        error = None
    except Exception as e:
        result_str = f"EXECUTION ERROR: {e}"
        error      = str(e)
        print(f"  ❌ {result_str}")

    # Generate natural-language answer from results
    if not error:
        answer_prompt = f"""The analyst asked: "{state['question']}"
The SQL returned these results:
{result_str}

Write a clear 2-3 sentence business answer using the actual numbers from the results.
Be specific. Use the exact figures from the data."""
        final_answer = call_bedrock(answer_prompt)
    else:
        final_answer = f"Query failed: {error}"

    result_summary = result_str[:300]
    memory.save_query(state["question"], state["sql_query"], result_summary, state["review_rounds"])

    trace_entry = f"[Executor] SQL ran successfully. {len(df) if not error else 0} rows."
    return {
        "execution_result": result_str,
        "final_answer":     final_answer,
        "error":            error,
        "reasoning_trace":  state["reasoning_trace"] + [trace_entry],
    }

# ── Conditional routing ───────────────────────────────────────────────────────
def route_after_review(state: SQLAgentState) -> str:
    if state["approved"]:
        return "execute"
    if state["review_rounds"] >= MAX_REVIEW_ROUNDS:
        print(f"\n⚠ Max review rounds ({MAX_REVIEW_ROUNDS}) reached. Executing best SQL available.")
        return "execute"
    return "generate"    # send back to generator with feedback

# ── Build the LangGraph ───────────────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(SQLAgentState)
    graph.add_node("generate", sql_generator_node)
    graph.add_node("review",   sql_reviewer_node)
    graph.add_node("execute",  sql_executor_node)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "review")
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {"generate": "generate", "execute": "execute"}
    )
    graph.add_edge("execute", END)
    return graph.compile()

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*70)
    print("DAY 10 — LAB 2: LangGraph 2-Agent SQL Workflow + Memory")
    print("Sigma DataTech Analytics Platform")
    print("="*70)

    app = build_graph()
    db_schema       = memory.get_schema()
    approved_results = []

    questions = [
        "Which payment methods are growing fastest this month compared to last month? Show percentage growth.",
        "Which 5 merchants have the highest refund rate? Show refund count and total transaction count.",
    ]

    for i, question in enumerate(questions, 1):
        print(f"\n{'─'*70}")
        print(f"QUESTION {i}: {question}")
        print(f"{'─'*70}")

        memory_context = memory.get_relevant_context(question)

        initial_state: SQLAgentState = {
            "question":         question,
            "memory_context":   memory_context,
            "db_schema":        db_schema,
            "sql_query":        "",
            "review_feedback":  "",
            "review_rounds":    0,
            "approved":         False,
            "execution_result": "",
            "final_answer":     "",
            "reasoning_trace":  [],
            "error":            None,
        }

        final_state = app.invoke(initial_state)

        approved_results.append({
            "question":       question,
            "final_sql":      final_state["sql_query"],
            "review_rounds":  final_state["review_rounds"],
            "approved":       final_state["approved"],
            "result_preview": final_state["execution_result"][:300],
            "answer":         final_state["final_answer"],
            "trace":          final_state["reasoning_trace"],
        })

        print(f"\n💡 BUSINESS ANSWER:\n{final_state['final_answer']}")

    # Save outputs
    trace_path = os.path.join(OUTPUT_DIR, "langgraph_trace.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(approved_results, f, indent=2, ensure_ascii=False)

    queries_path = os.path.join(OUTPUT_DIR, "approved_queries.json")
    with open(queries_path, "w", encoding="utf-8") as f:
        json.dump([{"q": r["question"], "sql": r["final_sql"], "rounds": r["review_rounds"]} for r in approved_results], f, indent=2)

    print(f"\n[SAVED] {trace_path}")
    print(f"[SAVED] {queries_path}")
    print(f"[SAVED] agent_memory.db  ← run this script again — agents will remember!")

    # ── Judgment question ─────────────────────────────────────────────────────
    print("\n" + "─"*60)
    rounds = [r["review_rounds"] for r in approved_results]
    print(f"Reviewer triggered {sum(1 for r in rounds if r>1)} re-generation(s) across {len(questions)} questions.")
    answer = input("In one sentence — what was the most important thing Agent 2 (the reviewer) caught? ").strip()
    if not answer:
        answer = "NOT ANSWERED"

    for r in approved_results:
        r["student_judgment"] = answer
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(approved_results, f, indent=2, ensure_ascii=False)

    print("\n✅ Lab 2 complete.")
    print("   LangGraph gave you: typed state, conditional routing, memory,")
    print("   multi-agent review, and a Snowflake swap in 4 lines.")
    print("   Lab 3: CrewAI — same concepts, different philosophy.")


# ═════════════════════════════════════════════════════════════════════════════
# STUDENT BUILD TASK — Build a LangGraph from scratch (no copy-paste from above)
# Time: 25–30 minutes  |  Mandatory before Lab 3
# ═════════════════════════════════════════════════════════════════════════════
#
# You just watched a 3-node LangGraph run. Now you build a 2-node one yourself.
#
# THE GRAPH YOU WILL BUILD:
#   Node 1 — sql_checker_node:   checks if a SQL query has a WHERE clause
#                                 (no LLM needed — pure Python logic)
#   Node 2 — safe_executor_node: runs the SQL if safe; blocks it if not
#
#   Routing after Node 1:
#     safe  → execute → END
#     unsafe → blocked → END    (same node handles both paths, different message)
#
# WHY THIS DESIGN:
#   Every production NL2SQL system needs a safety layer.
#   A full-table SELECT on 4M rows kills the warehouse.
#   This graph is that safety layer — simplified, but the pattern is real.
#
# SUCCESS CRITERION:
#   Test 1 (safe SQL with WHERE)  → returns actual data rows
#   Test 2 (unsafe SQL, no WHERE) → returns "BLOCKED: ..." message
#   Both must pass before you move to Lab 3.
# ─────────────────────────────────────────────────────────────────────────────

def student_build_task():

    print("\n" + "═"*70)
    print("STUDENT BUILD TASK — Build your own LangGraph from scratch")
    print("═"*70)
    print("""
Open the file:  2b_student_build.py

It contains a skeleton with 4 functions that have  pass  where your code goes.
Fill in every pass, then run:

    python 2b_student_build.py

Both test cases must pass:
  ✅ SAFE SQL   → returns actual data rows from DuckDB
  ❌ UNSAFE SQL → returns "BLOCKED: ..."

Show the trainer the output before moving to Lab 3.
""")

    print("The 3 concepts: TypedDict state + node functions + conditional edges.")
    print("That is the entire framework. Everything else is just more of these 3.")


if __name__ == "__main__":
    main()
    student_build_task()
