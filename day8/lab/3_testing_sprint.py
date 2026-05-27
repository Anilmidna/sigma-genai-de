"""
Day 8 — Sprint 3: Testing Sprint (pytest + Great Expectations)
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION BRIEFING:
  The pipeline is reviewed. The code is documented.
  But there are ZERO tests.

  Would you merge this to main? The tech lead won't.
  No test coverage = no merge. That's the rule at every serious
  data engineering team you will ever work for.

  Sprint 3 uses AI to generate BOTH a pytest code quality suite
  AND a Great Expectations data quality suite in under 2 minutes.

  The twist: AI will deliberately write at least one bad test.
  A test that looks correct but will miss a real production bug.
  YOUR job: find it, name it, explain why it is wrong.
  That is the skill that separates a senior DE from a junior one.

MANUAL FIRST (do this BEFORE running the script):
  Look at sample_data.py — specifically TRANSACTIONS_DIRTY.
  Pick ONE of the 7 dirty records and write ONE pytest assertion
  that would catch it. Just the assert line — 30 seconds max.
  Example: assert len(result) < len(TRANSACTIONS_DIRTY)
  THEN run the script and see what AI generates for the same data.

WHERE THIS FITS IN THE PLATFORM:
  Day 8 Sprint 2 (done):  AI documented the pipeline + runbook
  Day 8 Sprint 3 (now):   AI writes tests — including one bad one
  Day 8 Sprint 4 (next):  CI/SLO — tests run automatically on every push
  Day 12: The self-heal agent runs these same tests to decide
           whether a recovered pipeline is safe to promote to gold

HOW TO RUN:
  cd repo/day8/lab
  python 3_testing_sprint.py

OUTPUT:
  devops_brain/test_pipeline.py    <- AI-generated pytest suite
  devops_brain/ge_expectations.json <- Great Expectations suite (JSON)
  devops_brain/testing_report.json  <- combined results + your judgment

IMPORTANT: SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import inspect
import subprocess
import boto3
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(__file__))
from sample_data import (
    transform_bronze_to_silver,
    compute_merchant_performance,
    compute_daily_summary,
    TRANSACTIONS_CLEAN,
    TRANSACTIONS_DIRTY,
    MERCHANTS,
)

# ── Configuration ──────────────────────────────────────────────────────────
MODEL_ID_PRO  = "amazon.nova-pro-v1:0"
MODEL_ID_LITE = "amazon.nova-lite-v1:0"
REGION        = "us-east-1"

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "devops_brain")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Bedrock client ─────────────────────────────────────────────────────────
try:
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
except Exception as e:
    print(f"[ERROR] Could not create Bedrock client: {e}")
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def call_bedrock(model_id: str, system_text: str, user_text: str, max_tokens: int = 4000) -> tuple[str, dict]:
    """
    Invoke a Bedrock Nova model via the Converse API.

    Args:
        model_id:    The Bedrock model ID to invoke.
        system_text: System prompt setting the AI's role.
        user_text:   The user-turn prompt content.
        max_tokens:  Token budget for the response.

    Returns:
        Tuple of (response_text, usage_dict).
    """
    response = bedrock.converse(
        modelId=model_id,
        system=[{"text": system_text}],
        messages=[{"role": "user", "content": [{"text": user_text}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
    )
    text  = response["output"]["message"]["content"][0]["text"]
    usage = response["usage"]
    return text, usage


def strip_fences(text: str, fence_lang: str = "") -> str:
    """
    Remove markdown code fences from AI output.

    Args:
        text:       Raw AI response.
        fence_lang: Language tag to strip (e.g. "python", "json").

    Returns:
        Cleaned text with fences removed.
    """
    text = text.strip()
    tag = f"```{fence_lang}" if fence_lang else "```"
    if text.startswith(tag):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def get_function_sources() -> str:
    """
    Extract source code of the 3 pipeline functions for the AI prompt.

    Returns:
        Multi-line string with the source of all 3 functions concatenated.
    """
    funcs = [transform_bronze_to_silver, compute_merchant_performance, compute_daily_summary]
    sources = []
    for fn in funcs:
        sources.append(f"# {'─' * 50}\n# {fn.__name__}\n# {'─' * 50}\n{inspect.getsource(fn)}")
    return "\n\n".join(sources)


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Generate pytest suite (Nova Pro)
# ══════════════════════════════════════════════════════════════════════════

def generate_pytest_suite(function_sources: str) -> tuple[str, dict]:
    """
    Use Nova Pro to generate a pytest test suite with 8-10 tests.

    The prompt explicitly asks AI to include at least one intentionally
    wrong test — teaching students that AI-generated tests need review.

    Args:
        function_sources: Source code of the 3 pipeline functions.

    Returns:
        Tuple of (pytest_code_string, usage_dict).
    """
    system = (
        "You are a senior test engineer at a fintech company. "
        "You write pytest suites that catch real production bugs, not just happy-path tests. "
        "You follow the AAA pattern: Arrange, Act, Assert. "
        "You sometimes make deliberate mistakes to teach junior engineers to review AI output."
    )

    user = f"""Generate a complete pytest test file for these pipeline functions.

FUNCTIONS TO TEST (from sample_data.py):
{function_sources}

SAMPLE DATA (also importable from sample_data):
- TRANSACTIONS_CLEAN: 14 valid transaction dicts
- TRANSACTIONS_DIRTY: 7 dirty records:
    * None transaction_id (should be filtered)
    * negative amount (-50.00, should be filtered)
    * duplicate TXN012 (should be deduplicated)
    * MXXX unmatched merchant (UNMATCHED quality_flag expected)
    * zero amount 0.00 (valid — NOT filtered by current logic)
    * future date 2099-12-31 (valid — current logic does NOT filter future dates)
    * PENDING TXN015 (valid — PENDING is an accepted status)
- MERCHANTS: 8 merchant dicts (M001-M008, no MXXX)

REQUIREMENTS — write EXACTLY 9 test functions:

Tests for transform_bronze_to_silver (5 tests):
  1. test_null_transaction_id_filtered         - null IDs must not reach silver
  2. test_negative_amount_filtered             - negative amounts must not reach silver
  3. test_duplicate_transaction_id_deduplicated - TXN012 appears in both clean and dirty; only one copy in silver
  4. test_merchant_enrichment_clean_record     - a COMPLETED record gets merchant_name, category, city populated
  5. test_unmatched_merchant_gets_flag         - MXXX merchant gets quality_flag = "UNMATCHED"

Tests for compute_merchant_performance (3 tests):
  6. test_revenue_counts_only_completed        - FAILED transactions must NOT add to total_revenue
  7. test_failure_rate_calculation             - for a merchant with 1 failed out of 2 total: failure_rate_pct = 50.0
  8. test_merchant_performance_wrong_assertion - INTENTIONALLY WRONG: assert that zero-amount COMPLETED transactions
                                                  increase total_revenue by their amount (they do, which means this
                                                  test passes on current data but HIDES that zero-amount transactions
                                                  are probably data quality issues that should have been caught earlier)
                                                  Add a comment: # INTENTIONAL BUG: this test passes but proves nothing

Test for compute_daily_summary (1 test):
  9. test_unique_customer_count_per_date       - on 2024-01-15 there are 2 transactions (TXN001, TXN002) with
                                                  different customer_ids; unique_customers for that date must be 2

IMPORTANT RULES:
- Use pytest (function-based, no class)
- Import sample_data functions and data at the top of the file
- sys.path.insert(0, os.path.dirname(__file__) + "/../") at top so imports resolve
- sys.path.insert(0, os.path.dirname(__file__) + "/../../") as backup
- Each test must have a one-line docstring: what PRODUCTION scenario it guards against
- The intentionally wrong test (#8) must have a comment starting with: # INTENTIONAL BUG:
- Return ONLY Python code. No markdown. No explanation."""

    print("\n[Bedrock] Step 1: Generating pytest suite (8-10 tests)...")
    print(f"          Model: {MODEL_ID_PRO} — needs precise reasoning about test logic")

    code, usage = call_bedrock(MODEL_ID_PRO, system, user, max_tokens=4000)
    code = strip_fences(code, "python")

    print(f"          Done. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")
    print(f"          Tests generated: {code.count('def test_')}")
    return code, usage


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Run pytest programmatically
# ══════════════════════════════════════════════════════════════════════════

def run_pytest(test_file: str) -> dict:
    """
    Run pytest on the generated test file and capture pass/fail output.

    Uses subprocess to invoke pytest with verbose output and short
    tracebacks. Runs with a 60-second timeout to avoid hanging.

    Args:
        test_file: Absolute path to the generated test_pipeline.py.

    Returns:
        Dict with keys: returncode, stdout, stderr, passed, failed, errors.
    """
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=os.path.dirname(test_file),
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.stdout.count(" PASSED"),
            "failed": result.stdout.count(" FAILED"),
            "errors": result.stdout.count(" ERROR"),
        }
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "stdout": "", "stderr": "TIMEOUT after 60s", "passed": 0, "failed": 0, "errors": 1}
    except FileNotFoundError:
        return {"returncode": -1, "stdout": "", "stderr": "pytest not found — run: pip install pytest", "passed": 0, "failed": 0, "errors": 1}


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Generate Great Expectations suite (Nova Lite)
# ══════════════════════════════════════════════════════════════════════════

def generate_ge_suite() -> tuple[str, dict]:
    """
    Use Nova Lite to generate a Great Expectations expectation suite in JSON.

    The suite covers silver_transactions: no nulls in key columns, no
    negative amounts, no duplicates, row count bounds, and valid status values.

    Returns:
        Tuple of (ge_json_string, usage_dict).
    """
    system = (
        "You are a data quality engineer. "
        "You write Great Expectations expectation suites in valid JSON format. "
        "You produce only valid JSON — no Python code, no YAML, just JSON."
    )

    user = """Generate a Great Expectations expectation suite JSON for the silver_transactions table.

TABLE SCHEMA:
  transaction_id  VARCHAR NOT NULL
  amount          DOUBLE  NOT NULL  (must be >= 0 after silver filtering)
  status          VARCHAR NOT NULL  (allowed values: COMPLETED, FAILED, PENDING)
  merchant_id     VARCHAR           (nullable for unmatched)
  customer_id     VARCHAR
  transaction_date DATE NOT NULL
  payment_method  VARCHAR
  merchant_name   VARCHAR
  category        VARCHAR
  city            VARCHAR
  quality_flag    VARCHAR           (CLEAN or UNMATCHED)

DATA CONTEXT:
  - After Bronze -> Silver transform, we expect 18-22 rows
  - All transaction_ids must be non-null (nulls were filtered in Bronze)
  - All amounts must be >= 0 (negatives were filtered in Bronze)
  - No duplicate transaction_ids should exist in silver
  - quality_flag is either CLEAN or UNMATCHED (no other values)

GENERATE a valid Great Expectations expectation suite JSON with these expectations:
  1. expect_table_row_count_to_be_between (min_value: 10, max_value: 30)
  2. expect_column_values_to_not_be_null for: transaction_id, amount, status, transaction_date
  3. expect_column_values_to_be_between for amount (min_value: 0)
  4. expect_column_values_to_be_unique for transaction_id
  5. expect_column_values_to_be_in_set for status: ["COMPLETED", "FAILED", "PENDING"]
  6. expect_column_values_to_be_in_set for quality_flag: ["CLEAN", "UNMATCHED"]
  7. expect_column_mean_to_be_between for amount (min_value: 100, max_value: 5000)

Use standard GE JSON structure:
{
  "expectation_suite_name": "silver_transactions_suite",
  "expectations": [
    {
      "expectation_type": "...",
      "kwargs": {...},
      "meta": {"notes": "..."}
    }
  ],
  "meta": {
    "great_expectations_version": "0.18.x",
    "generated_by": "Nova Lite",
    "pipeline": "Sigma DataTech Bronze -> Silver"
  }
}

Return ONLY valid JSON. No explanation. No markdown fences."""

    print("\n[Bedrock] Step 3: Generating Great Expectations suite (JSON)...")
    print(f"          Model: {MODEL_ID_LITE} — JSON generation doesn't need Pro")

    ge_json_str, usage = call_bedrock(MODEL_ID_LITE, system, user, max_tokens=2000)
    ge_json_str = strip_fences(ge_json_str, "json")

    print(f"          Done. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")
    return ge_json_str, usage


# ══════════════════════════════════════════════════════════════════════════
# STEP 4 — Run GE checks via DuckDB SQL (fallback if GE not installed)
# ══════════════════════════════════════════════════════════════════════════

def run_ge_checks_via_duckdb(ge_suite: dict) -> dict:
    """
    Execute Great Expectations checks directly against in-memory DuckDB.

    This is the fallback path when great-expectations is not installed.
    We load the silver data computed by sample_data.py functions into
    DuckDB in-memory and run SQL equivalents of each expectation.

    Args:
        ge_suite: Parsed GE expectation suite as a Python dict.

    Returns:
        Dict with keys: checks (list), passed (int), failed (int), total (int).
    """
    try:
        import duckdb
    except ImportError:
        return {"error": "DuckDB not installed — run: pip install duckdb"}

    # Build silver data in-memory from sample_data functions
    all_txns = TRANSACTIONS_CLEAN + TRANSACTIONS_DIRTY
    silver_rows = transform_bronze_to_silver(all_txns, MERCHANTS)

    con = duckdb.connect(":memory:")
    con.execute("""
        CREATE TABLE silver_transactions (
            transaction_id  VARCHAR,
            amount          DOUBLE,
            status          VARCHAR,
            merchant_id     VARCHAR,
            customer_id     VARCHAR,
            transaction_date VARCHAR,
            payment_method  VARCHAR,
            merchant_name   VARCHAR,
            category        VARCHAR,
            city            VARCHAR,
            quality_flag    VARCHAR
        )
    """)
    for row in silver_rows:
        con.execute(
            "INSERT INTO silver_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [row.get("transaction_id"), row.get("amount"), row.get("status"),
             row.get("merchant_id"), row.get("customer_id"), str(row.get("transaction_date", "")),
             row.get("payment_method"), row.get("merchant_name"), row.get("category"),
             row.get("city"), row.get("quality_flag")],
        )

    checks = [
        ("row_count between 10 and 30",
         "SELECT COUNT(*) FROM silver_transactions",
         lambda v: 10 <= v <= 30),
        ("no null transaction_id",
         "SELECT COUNT(*) FROM silver_transactions WHERE transaction_id IS NULL",
         lambda v: v == 0),
        ("no null amount",
         "SELECT COUNT(*) FROM silver_transactions WHERE amount IS NULL",
         lambda v: v == 0),
        ("no null status",
         "SELECT COUNT(*) FROM silver_transactions WHERE status IS NULL",
         lambda v: v == 0),
        ("no null transaction_date",
         "SELECT COUNT(*) FROM silver_transactions WHERE transaction_date IS NULL",
         lambda v: v == 0),
        ("amount >= 0",
         "SELECT COUNT(*) FROM silver_transactions WHERE amount < 0",
         lambda v: v == 0),
        ("transaction_id unique",
         "SELECT COUNT(*) - COUNT(DISTINCT transaction_id) FROM silver_transactions",
         lambda v: v == 0),
        ("status values valid",
         "SELECT COUNT(*) FROM silver_transactions WHERE status NOT IN ('COMPLETED','FAILED','PENDING')",
         lambda v: v == 0),
        ("quality_flag values valid",
         "SELECT COUNT(*) FROM silver_transactions WHERE quality_flag NOT IN ('CLEAN','UNMATCHED')",
         lambda v: v == 0),
        ("mean amount between 100 and 5000",
         "SELECT AVG(amount) FROM silver_transactions",
         lambda v: v is not None and 100 <= v <= 5000),
    ]

    results = []
    passed = 0
    failed = 0
    for name, sql, assertion in checks:
        value = con.execute(sql).fetchone()[0]
        ok = assertion(value)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        display_val = f"{value:.2f}" if isinstance(value, float) else str(value)
        results.append({"check": name, "value": display_val, "status": status})

    con.close()
    return {"checks": results, "passed": passed, "failed": failed, "total": len(checks)}


# ══════════════════════════════════════════════════════════════════════════
# ACCOUNTABILITY GATE
# ══════════════════════════════════════════════════════════════════════════

def accountability_gate(pytest_result: dict) -> str:
    """
    After showing pytest results, ask the student one critical question.

    If tests failed: ask whether it is a code bug or a test bug.
    If all passed: ask the student to name the weakest test.

    Args:
        pytest_result: Dict returned by run_pytest().

    Returns:
        The student's answer as a string (or "NOT ANSWERED" if empty).
    """
    print()
    print("=" * 65)

    if pytest_result["failed"] > 0 or pytest_result["errors"] > 0:
        print("  One or more tests failed above.")
        print("  → Is this a CODE bug or a TEST bug?")
        print("    Explain in 1 sentence what you would fix:")
    else:
        print("  All tests passed.")
        print("  But are they GOOD tests?")
        print("  → Name the WEAKEST test and why it would miss a real bug:")

    print()
    try:
        answer = input("  Your answer: ").strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if not answer:
        answer = "NOT ANSWERED"

    print("=" * 65)
    return answer


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 65)
    print("  SPRINT 3: Testing Sprint — pytest + Great Expectations")
    print("  Sigma Intelligence Platform | Day 8")
    print("=" * 65)

    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print()
    print("  MANUAL FIRST — Before we run anything:")
    print("  Open sample_data.py and look at TRANSACTIONS_DIRTY.")
    print("  Pick ONE of the 7 dirty records.")
    print("  Write ONE pytest assert line that would catch it.")
    print("  Example:  assert len(result) < len(TRANSACTIONS_DIRTY)")
    print("  (30 seconds — just the assert, not a full test function)")
    print()
    input("  [Press Enter when you have your assert line ready] ")

    # ── Extract function sources ────────────────────────────────
    print("\n[INFO] Extracting pipeline function source code...")
    function_sources = get_function_sources()
    func_count = function_sources.count("def ")
    print(f"       Found {func_count} functions to test")

    total_usage = {"inputTokens": 0, "outputTokens": 0}

    # ── Step 1: Generate pytest suite ──────────────────────────
    test_code, usage1 = generate_pytest_suite(function_sources)
    total_usage["inputTokens"]  += usage1["inputTokens"]
    total_usage["outputTokens"] += usage1["outputTokens"]

    test_file = os.path.join(OUTPUT_DIR, "test_pipeline.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_code)
    print(f"\n[OK] Saved: devops_brain/test_pipeline.py")
    print(f"     Test functions: {test_code.count('def test_')}")
    print(f"     Lines: {len(test_code.splitlines())}")

    # ── Step 2: Run pytest ──────────────────────────────────────
    print("\n[INFO] Running pytest on generated test suite...")
    pytest_result = run_pytest(test_file)

    print("\n── pytest output ─────────────────────────────────────────")
    if pytest_result["stdout"]:
        # Show last 3000 chars so students see the failures clearly
        output = pytest_result["stdout"]
        if len(output) > 3000:
            print(f"  ... (truncated — showing last 3000 of {len(output)} chars)")
            output = output[-3000:]
        print(output)
    else:
        print("  (no stdout)")

    if pytest_result["stderr"] and "TIMEOUT" not in pytest_result["stderr"] and pytest_result["stderr"].strip():
        print("\n── stderr ────────────────────────────────────────────────")
        print(pytest_result["stderr"][-500:])

    print("\n── pytest summary ────────────────────────────────────────")
    print(f"  Passed: {pytest_result['passed']}")
    print(f"  Failed: {pytest_result['failed']}")
    print(f"  Errors: {pytest_result['errors']}")

    if pytest_result["failed"] > 0:
        print()
        print("  [EXPECTED] Some tests failed — that is the lesson.")
        print("  Open devops_brain/test_pipeline.py")
        print("  Find the failing test.")
        print("  Look for the comment: # INTENTIONAL BUG:")
    elif pytest_result["passed"] > 0:
        print()
        print("  [NOTE] All tests passed. But passing tests are not the same as GOOD tests.")
        print("  Look for the comment: # INTENTIONAL BUG: in test_pipeline.py")
        print("  That test passes but proves nothing useful.")

    # ── Accountability gate (after pytest) ─────────────────────
    student_judgment = accountability_gate(pytest_result)

    # ── Step 3: Generate GE expectations ───────────────────────
    ge_json_str, usage2 = generate_ge_suite()
    total_usage["inputTokens"]  += usage2["inputTokens"]
    total_usage["outputTokens"] += usage2["outputTokens"]

    # Validate and parse the GE JSON
    ge_suite = {}
    ge_json_valid = False
    try:
        ge_suite = json.loads(ge_json_str)
        ge_json_valid = True
    except json.JSONDecodeError as e:
        print(f"\n[WARN] AI returned invalid JSON for GE suite: {e}")
        print("       Saving raw output for inspection.")
        ge_json_str = json.dumps({"raw_ai_output": ge_json_str, "parse_error": str(e)}, indent=2)

    ge_path = os.path.join(OUTPUT_DIR, "ge_expectations.json")
    with open(ge_path, "w", encoding="utf-8") as f:
        f.write(ge_json_str if isinstance(ge_json_str, str) else json.dumps(ge_suite, indent=2))
    print(f"\n[OK] Saved: devops_brain/ge_expectations.json")
    if ge_json_valid:
        expectation_count = len(ge_suite.get("expectations", []))
        print(f"     Expectations defined: {expectation_count}")

    # ── Step 4: Run GE checks via DuckDB ───────────────────────
    print("\n[INFO] Running Great Expectations checks via DuckDB SQL fallback...")
    print("       (Use 'pip install great-expectations' for native GE runner)")
    dq_results = run_ge_checks_via_duckdb(ge_suite)

    if "error" in dq_results:
        print(f"\n[ERROR] {dq_results['error']}")
        dq_display = dq_results
    else:
        print()
        print(f"  {'Check':<45} {'Value':>8} {'Status':>6}")
        print(f"  {'-'*45} {'-'*8} {'-'*6}")
        for c in dq_results["checks"]:
            color_on  = "\033[92m" if c["status"] == "PASS" else "\033[91m"
            color_off = "\033[0m"
            print(f"  {c['check']:<45} {c['value']:>8} {color_on}{c['status']}{color_off}")
        print()
        print(f"  Total: {dq_results['total']} | "
              f"Passed: {dq_results['passed']} | "
              f"Failed: {dq_results['failed']}")
        dq_display = dq_results

    # ── Save combined testing report ────────────────────────────
    report = {
        "sprint": "testing_sprint",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models_used": {
            "pytest_suite": MODEL_ID_PRO,
            "ge_suite": MODEL_ID_LITE,
        },
        "token_usage": {
            "step1_pytest": {"input": usage1["inputTokens"], "output": usage1["outputTokens"]},
            "step2_ge":     {"input": usage2["inputTokens"], "output": usage2["outputTokens"]},
            "total_input":  total_usage["inputTokens"],
            "total_output": total_usage["outputTokens"],
        },
        "pytest": {
            "file": "devops_brain/test_pipeline.py",
            "tests_generated": test_code.count("def test_"),
            "passed": pytest_result["passed"],
            "failed": pytest_result["failed"],
            "errors": pytest_result["errors"],
            "all_green": pytest_result["returncode"] == 0,
        },
        "great_expectations": {
            "file": "devops_brain/ge_expectations.json",
            "json_valid": ge_json_valid,
            "duckdb_checks": dq_display,
        },
        "student_judgment": student_judgment,
    }

    report_path = os.path.join(OUTPUT_DIR, "testing_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\n[OK] Saved: devops_brain/testing_report.json")

    # ── Debrief ──────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT JUST HAPPENED:")
    print("    AI generated two independent quality safety nets:")
    print("      1. pytest suite — verifies that your transformation LOGIC")
    print("         does what the spec says (code correctness)")
    print("      2. Great Expectations suite — verifies that your DATA")
    print("         satisfies business invariants after the transform")
    print("    These two suites catch different classes of bugs.")
    print("    A pipeline can pass all pytest tests and still produce bad data.")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. pytest structure — imports, function naming (test_*), docstrings,")
    print("       direct use of sample_data constants as fixtures")
    print("    2. GE expectation types — row count, null checks, set membership,")
    print("       uniqueness — these are the most common DQ checks in production")
    print("    3. Including an intentionally wrong test — the # INTENTIONAL BUG:")
    print("       comment is your signal that AI was told to include a trap")
    print()
    print("  WHAT AI GETS WRONG (always check these):")
    print("    1. Expected values in tests — AI may compute wrong aggregates")
    print("       Example: 'assert total_revenue == 8755.0' when the real value")
    print("       depends on which DIRTY records you fed in; always verify manually")
    print("    2. GE threshold values — AI picks round numbers (min: 100, max: 5000)")
    print("       for mean amount; these may not match your actual data distribution")
    print("    3. Import paths in generated pytest files — AI often gets sys.path")
    print("       wrong when the test file lives in a subdirectory; always run once")
    print("       before committing to CI")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    AI writes tests in 60 seconds. A senior DE spots the bad one in 5.")
    print("    If you cannot spot a bad test, you are not ready to own the pipeline.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Sprint 4 (next): These tests become the gate in a CI/CD pipeline.")
    print("    Every push to main triggers them automatically.")
    print("    A failing test blocks the merge — not just prints a warning.")
    print(f"{'=' * 65}")
    print()
    print("  Next: python 4_ci_slo.py")
    print()


if __name__ == "__main__":
    main()
