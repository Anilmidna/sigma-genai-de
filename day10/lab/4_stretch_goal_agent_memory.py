"""
==============================================================================
DAY 10 — LAB 4 (STRETCH GOAL): SELF-HEALING PIPELINE AGENT
==============================================================================

MISSION BRIEFING
----------------
It's 2 AM. A Sigma DataTech pipeline crashes in production. Instead of paging
an on-call DE, your self-healing agent:
  1. Catches the failure
  2. Reads the error and the broken code
  3. Asks Bedrock to diagnose and patch it
  4. Re-runs the fixed code
  5. Saves the fix to persistent memory — so it NEVER makes the same call
     again at 3 AM

This is not a tutorial — it is a production pattern used at Databricks,
Astronomer, and AWS Step Functions. You are building a simplified version.

WHAT YOU WILL LEARN
-------------------
- Cross-run persistent memory: SQLite stores fixes, the next run reads them
- Error-driven agent loops: error IS the tool input, Bedrock IS the debugger
- Safe code patching: exec() sandboxed with timeout, no blind production runs
- Memory-informed generation: agent consults past fixes before writing new code
- Why self-healing pipelines are the next frontier in data platform reliability

MANUAL FIRST (3 minutes)
-------------------------
Below is a broken DuckDB pipeline snippet. Read it, find ALL bugs.
Write them on paper. Then watch the agent find and fix them autonomously.

NOTE: There are at least 3 obvious bugs below. Look harder — there may be more.
The agent will tell you how many it found. If your count differs, that is the lesson.

    conn = duckdb.connect("sigma_platform.duckdb")
    df = conn.execute("SELECT * FROM silver_transactions WHERE amount > 0").fetchdf()
    total = df["amounts"].sum()                                    # Bug 1 ?
    df2 = df.groupby("merchant_id").agg({"amount": "mean"}).reset_index()
    df2.columns = ["merchant_id", "avg_amount"]
    df2_sorted = df2.sort_values("avg_amounts", ascending=False)   # Bug 2 ?
    conn.close()
    print(f"Done. Total: {total:.2f}, Merchants: {len(df2)}")
    total_check = conn.execute("SELECT COUNT(*) FROM silver_transactions").fetchone()[0]  # Bug 3 ?
    print(f"Verified count: {total_check}")
    top = df2_sorted.iloc[0]["merchant"]                           # Bug 4 ?  (subtle)

==============================================================================
OUTPUT
------
  agent_outputs/healing_log.json      — full repair history with timestamps
  agent_outputs/patched_pipeline.py   — the fixed pipeline code
  agent_memory.db                     — shared SQLite (same DB as Lab 2)
==============================================================================
"""

import os, sys, json, sqlite3, textwrap, traceback, hashlib, duckdb
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
except ImportError:
    print("[ERROR] Run: pip install boto3")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
MODEL_ID   = "amazon.nova-pro-v1:0"
REGION     = "us-east-1"
DB_PATH    = os.path.join(os.path.dirname(__file__), "sigma_platform.duckdb")
MEM_DB     = os.path.join(os.path.dirname(__file__), "agent_memory.db")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_HEAL_ATTEMPTS = 4   # agent gives up after this many fix attempts

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "") -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 2000, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]

# ── Persistent Healing Memory ─────────────────────────────────────────────────
class HealingMemory:
    """
    Stores past fixes in SQLite — indexed by error fingerprint (error class +
    first line of traceback). Before generating a new fix, the agent checks if
    it has seen this error pattern before. This prevents duplicate LLM calls.
    """

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS healing_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                error_fingerprint TEXT NOT NULL,
                error_message TEXT,
                broken_code   TEXT,
                fixed_code    TEXT,
                fix_rationale TEXT,
                success       INTEGER DEFAULT 0,
                created_at    TEXT
            )
        """)
        self.conn.commit()

    def _fingerprint(self, error: str) -> str:
        """Stable fingerprint: exception message + the code line that caused it.
        Ignores file paths and line numbers — both change across runs."""
        lines = [l.strip() for l in error.splitlines() if l.strip()]
        # Last line = exception type + message e.g. "KeyError: 'amounts'"
        exception_line = lines[-1] if lines else error
        # Find the actual code line (not File/path lines, not ^^^ markers)
        code_lines = [l for l in lines
                      if not l.startswith("File ")
                      and not l.startswith("~")
                      and not l.startswith("^")
                      and not l.startswith("Traceback")]
        code_context = code_lines[-2] if len(code_lines) >= 2 else ""
        key = f"{exception_line} | {code_context}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def lookup(self, error: str) -> dict | None:
        """Return a previously successful fix for this error pattern, if any."""
        fp = self._fingerprint(error)
        row = self.conn.execute(
            "SELECT fixed_code, fix_rationale FROM healing_history WHERE error_fingerprint=? AND success=1 ORDER BY id DESC LIMIT 1",
            (fp,)
        ).fetchone()
        if row:
            return {"fixed_code": row[0], "fix_rationale": row[1], "from_memory": True}
        return None

    def save(self, error: str, broken_code: str, fixed_code: str, rationale: str, success: bool):
        fp = self._fingerprint(error)
        self.conn.execute(
            """INSERT INTO healing_history
               (error_fingerprint, error_message, broken_code, fixed_code, fix_rationale, success, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (fp, error[:1000], broken_code[:3000], fixed_code[:3000], rationale[:1000], int(success), datetime.now().isoformat())
        )
        self.conn.commit()

    def recall_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT error_fingerprint, error_message, success, created_at FROM healing_history ORDER BY id DESC LIMIT 10"
        ).fetchall()
        return [{"fp": r[0], "error": r[1][:80] + "...", "success": bool(r[2]), "at": r[3]} for r in rows]

    def close(self):
        self.conn.close()

# ── The broken pipeline (intentionally buggy) ─────────────────────────────────
BROKEN_PIPELINE = '''\
import duckdb, os

DB_PATH = r"<<<DB_PATH>>>"  # injected at runtime — safe across temp file execution
'''.replace("<<<DB_PATH>>>", DB_PATH) + '''\

def run_merchant_report():
    conn = duckdb.connect(DB_PATH)
    df = conn.execute("SELECT * FROM silver_transactions WHERE amount > 0").fetchdf()

    # Bug 1: wrong column name — "amounts" does not exist, should be "amount"
    total = df["amounts"].sum()

    df2 = df.groupby("merchant_id").agg({"amount": "mean"}).reset_index()
    df2.columns = ["merchant_id", "avg_amount"]

    # Bug 2: typo in column name — "avg_amounts" does not exist, should be "avg_amount"
    df2_sorted = df2.sort_values("avg_amounts", ascending=False)

    conn.close()
    print(f"Done. Total: {total:.2f}, Merchants: {len(df2)}")

    # Bug 3: conn already closed — cannot execute after close()
    total_check = conn.execute("SELECT COUNT(*) FROM silver_transactions").fetchone()[0]
    print(f"Verified count: {total_check}")

    # Bug 4 (subtle — only surfaces after 1-3 are fixed):
    # df2_sorted has columns ["merchant_id", "avg_amount"] but "merchant" does not exist
    top = df2_sorted.iloc[0]["merchant"]
    print(f"Top merchant by avg amount: {top}")

if __name__ == "__main__":
    run_merchant_report()
'''

# ── Safe code runner (sandboxed exec with timeout) ────────────────────────────
def safe_run(code: str, timeout_seconds: int = 15) -> tuple[bool, str]:
    """
    Execute code string safely. Returns (success, output_or_error).
    Uses a subprocess to enforce timeout and isolate exec().
    """
    import subprocess, tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=os.path.dirname(__file__),
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, (result.stderr or result.stdout).strip()
    except subprocess.TimeoutExpired:
        return False, f"TimeoutError: pipeline exceeded {timeout_seconds}s"
    except Exception as e:
        return False, f"RunnerError: {e}"
    finally:
        os.unlink(tmp_path)

# ── AI Debugger ───────────────────────────────────────────────────────────────
DEBUGGER_SYSTEM = """You are a senior Data Engineer debugging a Python pipeline.
You are given broken code and the exact error it produced.

Your job:
1. Identify ALL bugs (not just the one causing the current error — fix them all)
2. Return ONLY the corrected Python code — no explanation, no markdown fences
3. The code must be self-contained and runnable as a standalone script
4. Fix bugs using the simplest correct approach — remove unnecessary code if needed
5. If a DuckDB connection is read_only=True, do NOT attempt any write operations (CREATE, INSERT, DROP)
   — either remove the write block or open a separate writable connection

If you have seen a similar fix pattern before, apply it directly.
Return ONLY valid Python code starting with 'import' or '#'. No prose."""

def ai_fix(broken_code: str, error: str, past_fix_hint: str = "") -> tuple[str, str]:
    """Ask Bedrock to fix the pipeline. Returns (fixed_code, rationale)."""

    hint_block = ""
    if past_fix_hint:
        hint_block = f"\nRELEVANT PAST FIX (from memory):\n{past_fix_hint[:400]}\n"

    prompt = f"""The following Python pipeline is broken.

ERROR:
{error[:800]}

BROKEN CODE:
{broken_code}
{hint_block}
Fix ALL bugs and return only the corrected Python code."""

    raw = call_bedrock(prompt, system=DEBUGGER_SYSTEM)

    # Strip markdown fences if model adds them
    code = raw.strip()
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()

    # Extract rationale — ask a second, lightweight call
    rationale_prompt = f"""In ONE sentence, what was the root cause of this error?\n\nError: {error[:400]}\n\nAnswer in one sentence only."""
    rationale = call_bedrock(rationale_prompt)
    rationale = rationale.strip().split("\n")[0][:200]

    return code, rationale

# ── Self-Healing Loop ─────────────────────────────────────────────────────────
def heal(pipeline_code: str, memory: HealingMemory) -> dict:
    """
    Run the pipeline. If it fails, ask AI to fix it.
    Repeat up to MAX_HEAL_ATTEMPTS times.
    Consult memory before each AI call.
    """
    current_code = pipeline_code
    healing_log   = []
    start_time    = datetime.now().isoformat()

    print("\n" + "="*70)
    print("SELF-HEALING PIPELINE AGENT")
    print("Sigma DataTech — Autonomous Recovery System")
    print("="*70)

    # Show past healing history
    history = memory.recall_all()
    if history:
        print(f"\n[MEMORY] {len(history)} past healing event(s) on record:")
        for h in history[:3]:
            icon = "✅" if h["success"] else "❌"
            print(f"  {icon} {h['at'][:16]} — {h['error']}")

    last_failed_error = ""   # full error string from the previous failed attempt
    last_failed_code  = ""   # code that produced that error

    for attempt in range(1, MAX_HEAL_ATTEMPTS + 1):
        print(f"\n{'─'*60}")
        print(f"ATTEMPT {attempt}/{MAX_HEAL_ATTEMPTS} — Running pipeline...")

        success, output = safe_run(current_code)

        if success:
            print(f"✅ Pipeline succeeded on attempt {attempt}!")
            print(f"   Output: {output[:200]}")
            healing_log.append({
                "attempt": attempt,
                "status": "success",
                "output": output,
            })
            # Save successful fix — keyed on the FULL error from the previous failed run
            if attempt > 1:
                memory.save(
                    error=last_failed_error,
                    broken_code=last_failed_code,
                    fixed_code=current_code,
                    rationale=healing_log[-2].get("rationale", ""),
                    success=True,
                )
            break

        # ── Pipeline failed ───────────────────────────────────────────────────
        print(f"❌ Failed. Error:\n   {output[:300]}")

        # Track full error for the success-save fingerprint (must not be truncated)
        last_failed_error = output
        last_failed_code  = current_code

        # Check memory for a known fix
        cached = memory.lookup(output)
        if cached:
            print(f"[MEMORY] Known fix found! Applying from memory (no LLM call needed).")
            fixed_code = cached["fixed_code"]
            rationale  = cached["fix_rationale"] + " [from memory]"
        else:
            print(f"[AI] No cached fix. Calling Bedrock to diagnose...")
            hint = healing_log[-1]["rationale"] if healing_log and "rationale" in healing_log[-1] else ""
            fixed_code, rationale = ai_fix(current_code, output, past_fix_hint=hint)
            print(f"[AI] Diagnosis: {rationale}")

        healing_log.append({
            "attempt": attempt,
            "status": "failed",
            "error": output[:600],
            "rationale": rationale,
            "code_tried": current_code,
            "from_memory": bool(cached),
        })

        # Save failed attempt (success=False) — still useful for lookup patterns
        memory.save(
            error=output,
            broken_code=current_code,
            fixed_code=fixed_code,
            rationale=rationale,
            success=False,
        )

        current_code = fixed_code

    else:
        print(f"\n⚠ Agent exhausted {MAX_HEAL_ATTEMPTS} attempts. Escalating to on-call.")
        healing_log.append({"attempt": MAX_HEAL_ATTEMPTS + 1, "status": "escalated"})

    return {
        "start_time": start_time,
        "end_time": datetime.now().isoformat(),
        "total_attempts": len(healing_log),
        "final_status": healing_log[-1]["status"],
        "healing_log": healing_log,
        "final_code": current_code,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    memory = HealingMemory(MEM_DB)

    # ── Manual-first pause ────────────────────────────────────────────────────
    print("\n" + "="*70)
    print("DAY 10 — LAB 4 (STRETCH GOAL): Self-Healing Pipeline Agent")
    print("="*70)
    print("\n[MANUAL FIRST] The broken pipeline is printed at the top of this file.")
    print("You have 3 minutes: find all bugs on paper. Then press Enter.")
    input("  → Ready? Press Enter to start the agent: ")

    # ── Run healing loop ──────────────────────────────────────────────────────
    result = heal(BROKEN_PIPELINE, memory)

    # ── Save outputs ──────────────────────────────────────────────────────────
    log_path = os.path.join(OUTPUT_DIR, "healing_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    patch_path = os.path.join(OUTPUT_DIR, "patched_pipeline.py")
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(f"# Patched by Self-Healing Agent — {result['end_time']}\n")
        f.write(f"# Attempts needed: {result['total_attempts']}\n\n")
        f.write(result["final_code"])

    print(f"\n[SAVED] {log_path}")
    print(f"[SAVED] {patch_path}")
    print(f"[SAVED] {MEM_DB}  ← memory persists; re-run and watch attempt 1 use cache")

    memory.close()

    # ── Debrief ───────────────────────────────────────────────────────────────
    print("\n" + "─"*60)
    print("JUDGMENT QUESTION:")
    print("─"*60)
    print("The agent fixed 3 bugs across multiple LLM calls.")
    print("On a second run, cached fixes mean ZERO LLM calls for known errors.")
    print()
    answer = input(
        "In one sentence — what is the biggest risk of letting an AI auto-patch\n"
        "and auto-run code in a production pipeline? "
    ).strip()
    if not answer:
        answer = "NOT ANSWERED"

    result["student_judgment"] = answer
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n✅ Lab 4 complete. You built a self-healing pipeline.")
    print("   On Day 11: connect this to your Airflow DAG for real auto-recovery.")
    print("   Production version: use Step Functions + SNS for escalation instead of print().")

    # ── Summary stats ─────────────────────────────────────────────────────────
    total_heals = len([e for e in result["healing_log"] if e["status"] == "failed"])
    from_mem    = len([e for e in result["healing_log"] if e.get("from_memory")])
    print(f"\n   Attempts: {result['total_attempts']}  |  "
          f"AI calls: {total_heals - from_mem}  |  "
          f"From cache: {from_mem}  |  "
          f"Final: {result['final_status'].upper()}")


# ═════════════════════════════════════════════════════════════════════════════
# STUDENT BUILD TASK — Write your own broken pipeline, run the healer on it
# Time: 20–25 minutes  |  Stretch goal — do this if you finish Lab 4 early
# ═════════════════════════════════════════════════════════════════════════════
#
# The healer fixed a pre-written broken pipeline. Now the question is:
# what breaks a self-healing agent? What can it fix and what can it not?
#
# YOUR TASK: Write a broken pipeline yourself and find the healer's limits.
#
# RULES FOR YOUR BROKEN PIPELINE:
#   ▸ Must use sigma_platform.duckdb (same DB as all labs)
#   ▸ Must have at least 2 Python runtime bugs (KeyError, AttributeError, etc.)
#   ▸ Must have at least 1 SQL/data logic bug that causes WRONG RESULTS
#     but NOT a Python exception (e.g., wrong column in GROUP BY, no NULL filter)
#   ▸ No infinite loops, no network calls, no file deletions
#
# PREDICTION (write this before you run):
#   The agent will catch your Python runtime bugs (it sees the traceback).
#   The agent will likely MISS your SQL logic bug (no exception, no signal).
#   Verify this hypothesis with your own pipeline.
#
# SUCCESS CRITERION:
#   healing_log_v2.json must exist.
#   You can explain which bugs the agent caught and which it missed — and why.
# ─────────────────────────────────────────────────────────────────────────────

def student_build_task():

    print("\n" + "═"*70)
    print("STUDENT BUILD TASK — Write a broken pipeline, test the healer's limits")
    print("═"*70)
    print("""
WHAT TO DO:
  Step 1 — Write BROKEN_PIPELINE_V2 (a multi-line string, like BROKEN_PIPELINE above)
            Include: 2 Python runtime bugs + 1 silent logic bug
            Add a comment for each bug so you can verify after
  Step 2 — Run the healer against your pipeline (uncomment block below)
  Step 3 — Inspect agent_memory.db to see what was cached
  Step 4 — Run the healer a SECOND time with the same pipeline
            Observe: how many LLM calls this time? Why?

THE KEY HYPOTHESIS TO TEST:
  Self-healing agents fix Python errors (tracebacks give a clear signal).
  They CANNOT fix logic bugs (the code runs, but the answer is wrong).
  A wrong GROUP BY, a missing NULL filter, an off-by-one date range —
  these produce no exception. The agent declares success. The data is wrong.
  This is the most dangerous failure mode in production AI pipelines.
""")

    # ── STEP 1: Write your broken pipeline ────────────────────────────────────
    # Replace None with a multi-line string containing your broken Python code.
    # Use the Sigma DataTech schema. Comment each bug so you can verify later.
    #
    # HINT for a good logic bug:
    #   df.groupby("merchant_id").agg({"amount": "sum"})
    #   → add a wrong filter BEFORE the groupby that silently drops rows
    #   → the groupby still runs, the output looks fine, but totals are wrong

    BROKEN_PIPELINE_V2 = None  # ← replace with your triple-quoted pipeline string

    # ── STEP 2: Run the healer ────────────────────────────────────────────────
    # Uncomment when Step 1 is done:

    # if BROKEN_PIPELINE_V2 is None:
    #     print("❌ BROKEN_PIPELINE_V2 is None — complete Step 1 first.")
    #     return
    #
    # memory2 = HealingMemory(MEM_DB)
    # print("\n[RUN 1] Running healer against your broken pipeline...")
    # result2 = heal(BROKEN_PIPELINE_V2, memory2)
    # memory2.close()
    #
    # log2_path = os.path.join(OUTPUT_DIR, "healing_log_v2.json")
    # with open(log2_path, "w", encoding="utf-8") as f:
    #     json.dump(result2, f, indent=2, ensure_ascii=False)
    # print(f"\n[SAVED] {log2_path}")
    # ai_calls = len([e for e in result2["healing_log"] if not e.get("from_memory")])
    # print(f"Status: {result2['final_status']}  |  Attempts: {result2['total_attempts']}  |  LLM calls: {ai_calls}")

    # ── STEP 3: Inspect the memory cache ──────────────────────────────────────
    # Run this after Step 2 to see what the healer cached:

    # import sqlite3
    # mem_conn = sqlite3.connect(MEM_DB)
    # rows = mem_conn.execute(
    #     "SELECT error_fingerprint, substr(error_message,1,60) AS err, success, created_at "
    #     "FROM healing_history ORDER BY id DESC LIMIT 8"
    # ).fetchall()
    # print("\n── agent_memory.db contents (latest 8 rows) ────────────────────")
    # for fp, err, ok, ts in rows:
    #     print(f"  {'✅' if ok else '❌'}  {ts[:16]}  fp={fp}  {err}...")
    # mem_conn.close()

    # ── STEP 4: Second run — observe cache hit behaviour ─────────────────────
    # Uncomment after Step 2:

    # memory3 = HealingMemory(MEM_DB)
    # print("\n[RUN 2] Running healer again with the SAME broken pipeline...")
    # result3 = heal(BROKEN_PIPELINE_V2, memory3)
    # memory3.close()
    # ai_calls_2 = len([e for e in result3["healing_log"] if not e.get("from_memory")])
    # cached_2   = len([e for e in result3["healing_log"] if e.get("from_memory")])
    # print(f"\nRun 2:  LLM calls = {ai_calls_2}  |  From cache = {cached_2}")
    # print("If cache > 0: the memory system worked. Same error, zero LLM cost.")

    # ── STEP 5: Reflection ────────────────────────────────────────────────────
    # try:
    #     q1 = input("\n1. Which of your bugs did the agent miss, and why? ").strip()
    #     q2 = input("2. In production, how would you catch the logic bug the agent missed? ").strip()
    # except EOFError:
    #     q1 = q2 = "NOT ANSWERED"
    # print(f"\nLogged. Show healing_log_v2.json + your answers to the trainer.")

    print("\nComplete Steps 1–5. The key finding: tracebacks = fixable. Silent wrong data = not.")
    print("That distinction defines where you MUST keep humans in the loop.")


if __name__ == "__main__":
    main()
    student_build_task()
