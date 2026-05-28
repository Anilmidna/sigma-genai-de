"""
==============================================================================
DAY 8 — SPRINT 6: COMPETITIVE BUILD (60-Minute Ship-or-Doesn't-Ship)
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech's platform team just received a pull request from a new hire.
Nobody has reviewed it yet. The pipeline has never been run end-to-end in prod.

Your team has 60 minutes.

Run all five DevOps Brain tools against the challenge pipeline below.
Fix what you can. Then call Anil over.

He will look at one screen per team and say two words: SHIP or DOESN'T SHIP.

This is what a senior DE does on every PR review.
You now have the tools. Prove you can use them.

==============================================================================

OUTPUT FILES
------------
  labs/competitive_build/challenge_pipeline.py  — the new pipeline to review
  labs/output/code_review.json                  — Sprint 1 findings
  labs/output/test_results.json                 — Sprint 3 test run
  labs/output/slo_priority.json                 — Sprint 5 SLO priority
  labs/output/competitive_scorecard.json        — final verdict + student judgment (tracked by Vercel)

==============================================================================
"""

import sys
import os
import json
import re
import subprocess
import tempfile
from datetime import datetime

# Windows UTF-8 stdout fix
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
except ImportError:
    print("[ERROR] boto3 not installed. Run: pip install boto3")
    sys.exit(1)

# ── Model / region ────────────────────────────────────────────────────────────
MODEL_ID_LITE = "amazon.nova-lite-v1:0"
REGION        = "us-east-1"

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR      = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "output"))
COMPETITIVE_DIR = OUTPUT_DIR   # all sprint outputs go to labs/output/
CHALLENGE_PATH  = os.path.join(SCRIPT_DIR, "challenge_pipeline.py")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── ANSI colour helpers ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def green(s):  return f"{GREEN}{s}{RESET}"
def yellow(s): return f"{YELLOW}{s}{RESET}"
def red(s):    return f"{RED}{s}{RESET}"
def bold(s):   return f"{BOLD}{s}{RESET}"


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — CREATE THE CHALLENGE PIPELINE
# Four planted bugs students have NOT seen before.
# ══════════════════════════════════════════════════════════════════════════════

CHALLENGE_PIPELINE_CODE = '''\
"""
challenge_pipeline.py — Sigma DataTech Bronze→Silver loader (new hire PR)

Loads raw transaction CSV from S3, applies Silver-layer quality rules,
and writes results to DuckDB. Submitted for code review — not yet merged.
"""

import os
import json
import logging
from datetime import date
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
'''

# Inject the correct datetime import so the pipeline at least parses cleanly
# (the bug is that the *code* doesn't import datetime, not that we can't write the file)
CHALLENGE_PIPELINE_CODE = CHALLENGE_PIPELINE_CODE.replace(
    "from datetime import date\n",
    "from datetime import date\n# NOTE: datetime.datetime is used in apply_silver_rules but NOT imported — NameError at runtime\n",
)


def create_challenge_pipeline():
    """Write the challenge pipeline to devops_brain/challenge_pipeline.py."""
    with open(CHALLENGE_PATH, "w", encoding="utf-8") as f:
        f.write(CHALLENGE_PIPELINE_CODE)
    print(f"[SETUP] Challenge pipeline written: {CHALLENGE_PATH}")
    print("        Four bugs planted — students have NOT seen these before.\n")


# ══════════════════════════════════════════════════════════════════════════════
# BEDROCK HELPER
# ══════════════════════════════════════════════════════════════════════════════

def call_nova_lite(client, system_prompt: str, user_message: str) -> str:
    """Call Bedrock Nova Lite and return the response text."""
    body = {
        "messages": [
            {"role": "user", "content": [{"text": user_message}]}
        ],
        "system": [{"text": system_prompt}],
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0.2,
        },
    }
    response = client.invoke_model(
        modelId=MODEL_ID_LITE,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def strip_fences(text: str) -> str:
    text = re.sub(r"```(?:json|python|text|yaml)?\n?", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 1 — CODE REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def check_code_review(client) -> dict:
    """
    Ask Bedrock Nova Lite to review challenge_pipeline.py.
    PASS if the AI identifies at least 3 of the 4 planted bugs.
    """
    print(bold("CHECK 1 — Code Review (Nova Lite on challenge_pipeline.py)"))

    with open(CHALLENGE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    system_prompt = (
        "You are a senior data engineering code reviewer. "
        "Review Python pipeline scripts for bugs, missing imports, logic errors, "
        "and production anti-patterns. Be precise. Cite the function name or line. "
        "Classify each finding as CRITICAL, HIGH, or MEDIUM."
    )

    user_message = f"""Review the following Python pipeline script.

For each issue found:
- Assign severity: CRITICAL, HIGH, or MEDIUM
- Name the function or approximate line
- One-sentence problem description
- One-sentence fix recommendation

Use this format:
[SEVERITY] — Short title
  Location: <function name or line area>
  Problem: <one sentence>
  Fix: <one sentence>

---
SCRIPT:
---
{source}
"""

    print("  Calling Bedrock Nova Lite...")
    raw = call_nova_lite(client, system_prompt, user_message)
    review_text = strip_fences(raw)

    # Count severity hits
    upper = review_text.upper()
    critical_count = upper.count("[CRITICAL]")
    high_count     = upper.count("[HIGH]")
    total_findings = critical_count + high_count + upper.count("[MEDIUM]")

    # Heuristic: did the AI spot the four planted bugs?
    # Check for keywords associated with each bug
    bug_keywords = [
        ["requests", "import", "requirement"],   # Bug 1: missing dep
        ["off-by-one", ">=", "cutoff", "filter_recent", "date filter", "extra day"],  # Bug 2
        ["datetime", "nameError", "not imported", "undefined", "apply_silver"],        # Bug 3
        ["swallow", "silent", "exception", "re-rais", "load_to_silver", "data loss"],  # Bug 4
    ]
    bugs_found = 0
    for keywords in bug_keywords:
        if any(k.lower() in review_text.lower() for k in keywords):
            bugs_found += 1

    passed = bugs_found >= 3

    status_str = green("PASS") if passed else red("FAIL")
    print(f"  AI findings: {total_findings} total | Planted bugs caught: {bugs_found}/4")
    print(f"  Result: [{status_str}]  (need 3+, got {bugs_found})\n")

    result = {
        "check": "code_review",
        "model": MODEL_ID_LITE,
        "total_findings": total_findings,
        "critical": critical_count,
        "high": high_count,
        "planted_bugs_caught": bugs_found,
        "pass_threshold": 3,
        "passed": passed,
        "review": review_text,
    }

    out_path = os.path.join(COMPETITIVE_DIR, "code_review.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 2 — DOCUMENTATION
# ══════════════════════════════════════════════════════════════════════════════

def check_documentation(client) -> dict:
    """
    PASS if at least 50% of functions in challenge_pipeline.py have a docstring
    added by the student (i.e., a triple-quoted string within 2 lines of 'def ').
    The AI scores the original — students must manually add docstrings to pass.
    """
    print(bold("CHECK 2 — Documentation (docstring coverage on challenge_pipeline.py)"))

    with open(CHALLENGE_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Count functions and which ones have a following docstring within 2 lines
    func_indices = [i for i, l in enumerate(lines) if l.lstrip().startswith("def ")]
    total_funcs  = len(func_indices)

    documented = 0
    for idx in func_indices:
        # Look at the next 1–3 lines (after the def line and possible colon continuation)
        window = lines[idx + 1 : idx + 4]
        for wline in window:
            stripped = wline.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                documented += 1
                break

    coverage_pct = (documented / total_funcs * 100) if total_funcs > 0 else 0.0
    passed       = coverage_pct >= 50.0

    # Bedrock scores the original for context — printed but not used in pass/fail
    system_prompt = (
        "You are a Python code documentation reviewer. "
        "Score code documentation quality on a scale 0–10. "
        "10 = every function has a detailed docstring and type hints. "
        "0 = no docstrings, no type hints whatsoever."
    )
    user_message = (
        "Score the documentation quality of this pipeline (0–10). "
        "Reply with ONLY a JSON object: {\"score\": <number>, \"reason\": \"<one sentence>\"}\n\n"
        f"{open(CHALLENGE_PATH, encoding='utf-8').read()}"
    )

    doc_score = None
    doc_reason = ""
    try:
        print("  Calling Bedrock Nova Lite for documentation score...")
        raw = call_nova_lite(client, system_prompt, user_message)
        parsed = json.loads(strip_fences(raw))
        doc_score  = parsed.get("score")
        doc_reason = parsed.get("reason", "")
        print(f"  AI doc score: {doc_score}/10 — {doc_reason}")
    except Exception:
        print("  (Could not parse AI doc score — proceeding with static check)")

    status_str = green("PASS") if passed else red("FAIL")
    print(f"  Functions with docstrings: {documented}/{total_funcs} ({coverage_pct:.0f}%)")
    print(f"  Result: [{status_str}]  (need ≥50%, got {coverage_pct:.0f}%)")
    if not passed:
        print("  → Manually add docstrings to at least half the functions and re-run.\n")
    else:
        print()

    result = {
        "check": "documentation",
        "total_functions": total_funcs,
        "documented_functions": documented,
        "coverage_pct": round(coverage_pct, 1),
        "pass_threshold_pct": 50,
        "ai_doc_score": doc_score,
        "ai_doc_reason": doc_reason,
        "passed": passed,
    }
    return result


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 3 — TESTING
# ══════════════════════════════════════════════════════════════════════════════

def check_testing(client) -> dict:
    """
    Generate 3 quick pytest tests via Bedrock, write to a temp file, run pytest.
    PASS if at least 2 tests execute (even if some fail — tests must exist and run).
    """
    print(bold("CHECK 3 — Testing (AI generates 3 tests, pytest runs them)"))

    with open(CHALLENGE_PATH, "r", encoding="utf-8") as f:
        source = f.read()

    system_prompt = (
        "You are a senior data engineer writing pytest unit tests. "
        "Write concise, runnable tests that do NOT need a live database. "
        "Use only the Python standard library and pytest. No mocking libraries."
    )

    user_message = f"""Write exactly 3 pytest unit tests for the functions in this pipeline.

Focus on:
1. filter_recent_transactions — test the off-by-one boundary (date == cutoff vs date > cutoff)
2. apply_silver_rules — test that a None transaction_id is filtered out
3. apply_silver_rules — test that a negative amount is filtered out

Rules:
- Each test function must start with test_
- Tests must be self-contained (define their own input data inline)
- Do NOT use the actual challenge_pipeline module — copy the function logic inline or test it directly
- Output ONLY the Python test code, no markdown fences, no explanation

Inline the logic of filter_recent_transactions and apply_silver_rules directly
into the test file so it runs without any imports from challenge_pipeline.
"""

    print("  Calling Bedrock Nova Lite to generate tests...")
    raw = call_nova_lite(client, system_prompt, user_message)
    test_code = strip_fences(raw)

    # Ensure the test code has proper imports
    if "from datetime import" not in test_code and "import datetime" not in test_code:
        test_code = "from datetime import date, datetime\n" + test_code

    # Write to a temp file inside competitive dir
    test_file = os.path.join(COMPETITIVE_DIR, "test_challenge_pipeline.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_code)
    print(f"  Tests written: {test_file}")

    # Run pytest
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short", "--no-header", "-q"],
            capture_output=True, text=True, timeout=30,
            cwd=SCRIPT_DIR,
        )
        output = proc.stdout + proc.stderr

        # Count tests that were collected and ran (passed or failed — not errors)
        passed_count = output.count(" passed") + output.count(" PASSED")
        failed_count = output.count(" failed") + output.count(" FAILED")
        error_count  = output.count(" error")
        ran          = passed_count + failed_count

        passed = ran >= 2

        status_str = green("PASS") if passed else red("FAIL")
        print(f"  pytest: {passed_count} passed, {failed_count} failed, {error_count} errors")
        print(f"  Result: [{status_str}]  (need ≥2 running tests, got {ran})\n")

        result = {
            "check": "testing",
            "test_file": test_file,
            "tests_ran": ran,
            "passed": passed_count,
            "failed": failed_count,
            "errors": error_count,
            "pass_threshold": 2,
            "check_passed": passed,
            "pytest_output": output[-1000:],
        }

    except subprocess.TimeoutExpired:
        print(f"  [{red('FAIL')}] pytest timed out after 30 seconds\n")
        result = {
            "check": "testing",
            "test_file": test_file,
            "tests_ran": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "pass_threshold": 2,
            "check_passed": False,
            "pytest_output": "TIMEOUT",
        }

    except Exception as e:
        print(f"  [{red('ERROR')}] Could not run pytest: {e}\n")
        result = {
            "check": "testing",
            "test_file": "",
            "tests_ran": 0,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "pass_threshold": 2,
            "check_passed": False,
            "pytest_output": str(e),
        }

    out_path = os.path.join(COMPETITIVE_DIR, "test_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    return result


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 4 — CI / SLO FILES
# ══════════════════════════════════════════════════════════════════════════════

def check_ci_slo() -> dict:
    """
    PASS if both pipeline_ci.yml and slo_definitions.json exist in devops_brain/.
    Reuse from earlier sprints is intentional — the CI config covers any pipeline.
    """
    print(bold("CHECK 4 — CI/SLO (pipeline_ci.yml + slo_definitions.json exist)"))

    ci_candidates = [
        os.path.join(DEVOPS_BRAIN_DIR, "pipeline_ci.yml"),
        os.path.join(SCRIPT_DIR, ".github", "workflows", "pipeline_ci.yml"),
        os.path.join(os.path.dirname(SCRIPT_DIR), ".github", "workflows", "pipeline_ci.yml"),
    ]
    slo_path = os.path.join(DEVOPS_BRAIN_DIR, "slo_definitions.json")

    ci_exists  = any(os.path.exists(p) for p in ci_candidates)
    slo_exists = os.path.exists(slo_path)

    ci_found_at  = next((p for p in ci_candidates if os.path.exists(p)), None)
    passed = ci_exists and slo_exists

    ci_label  = green(f"EXISTS ({ci_found_at})")  if ci_exists  else red("MISSING — run Sprint 4 (ci_sprint)")
    slo_label = green(f"EXISTS ({slo_path})")     if slo_exists else red("MISSING — run Sprint 4 (ci_sprint)")

    print(f"  pipeline_ci.yml  : {ci_label}")
    print(f"  slo_definitions  : {slo_label}")

    status_str = green("PASS") if passed else red("FAIL")
    print(f"  Result: [{status_str}]\n")

    return {
        "check": "ci_slo",
        "ci_yml_found": ci_exists,
        "ci_yml_path": ci_found_at,
        "slo_json_found": slo_exists,
        "passed": passed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# CHECK 5 — OBSERVABILITY
# ══════════════════════════════════════════════════════════════════════════════

def check_observability(client, code_review_result: dict) -> dict:
    """
    PASS if devops_brain/observability_report.json exists from Sprint 5.
    Also asks Nova Lite: given the bugs in the challenge pipeline, which SLO
    matters most? Saves the one-sentence answer to slo_priority.json.
    """
    print(bold("CHECK 5 — Observability (observability_report.json + SLO priority)"))

    obs_path = os.path.join(DEVOPS_BRAIN_DIR, "observability_report.json")
    obs_exists = os.path.exists(obs_path)

    obs_label = green(f"EXISTS ({obs_path})") if obs_exists else red("MISSING — run Sprint 5 (observability_sprint)")
    print(f"  observability_report.json: {obs_label}")

    # Ask Nova Lite for SLO priority based on the discovered bugs
    review_snippet = code_review_result.get("review", "")[:800]
    bugs_summary = (
        "1. Missing 'requests' import — will cause ImportError in CI. "
        "2. Off-by-one in date filter (>=) — includes one extra day every run. "
        "3. datetime.datetime used but not imported — NameError at runtime. "
        "4. Exception handler swallows errors silently — invisible data loss."
    )

    system_prompt = (
        "You are an SRE on a data engineering platform. "
        "You define SLOs to catch production failures early. "
        "Be crisp — one sentence only."
    )
    user_message = (
        f"This pipeline has four bugs:\n{bugs_summary}\n\n"
        "Which is the single highest-priority SLO to monitor first, and why? "
        "Reply in ONE sentence."
    )

    slo_priority_text = ""
    try:
        print("  Calling Bedrock Nova Lite for SLO priority...")
        raw = call_nova_lite(client, system_prompt, user_message)
        slo_priority_text = strip_fences(raw).strip()
        print(f"  SLO priority: {slo_priority_text}\n")
    except Exception as e:
        slo_priority_text = f"(Bedrock call failed: {e})"
        print(f"  [{yellow('WARN')}] Could not get SLO priority: {e}\n")

    slo_result = {
        "check": "slo_priority",
        "bugs_used": bugs_summary,
        "slo_priority": slo_priority_text,
        "model": MODEL_ID_LITE,
    }
    slo_path = os.path.join(COMPETITIVE_DIR, "slo_priority.json")
    with open(slo_path, "w", encoding="utf-8") as f:
        json.dump(slo_result, f, indent=2, ensure_ascii=False)

    passed = obs_exists
    status_str = green("PASS") if passed else red("FAIL")
    print(f"  Result: [{status_str}]\n")

    return {
        "check": "observability",
        "obs_report_found": obs_exists,
        "slo_priority": slo_priority_text,
        "passed": passed,
    }


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — FINAL SCORECARD
# ══════════════════════════════════════════════════════════════════════════════

def print_scorecard(checks: list) -> int:
    """Print the formatted scorecard table and return total score (0–5)."""
    labels = [
        "CHECK 1  Code Review    (AI finds ≥3/4 bugs)",
        "CHECK 2  Documentation  (≥50% functions have docstrings)",
        "CHECK 3  Testing        (≥2 pytest tests run)",
        "CHECK 4  CI/SLO         (pipeline_ci.yml + slo_definitions.json exist)",
        "CHECK 5  Observability  (observability_report.json exists)",
    ]

    score = 0
    print("\n" + "=" * 68)
    print(bold("  FINAL SCORECARD — Sigma DataTech DevOps Brain"))
    print("=" * 68)

    for i, (label, check) in enumerate(zip(labels, checks)):
        passed = check.get("passed") or check.get("check_passed", False)
        mark   = green("PASS ✓") if passed else red("FAIL ✗")
        print(f"  [{mark}]  {label}")
        if passed:
            score += 1

    print("=" * 68)
    print(f"  TOTAL SCORE: {bold(str(score))}/5")

    if score == 5:
        verdict = "SHIP"
        print(f"\n  {green(bold('SHIP ✓'))}  All five checks green. Push the PR.")
    elif score >= 3:
        verdict = "CONDITIONAL SHIP"
        print(f"\n  {yellow(bold('CONDITIONAL SHIP'))}  Fix the red items above before merging.")
    else:
        verdict = "DOESN'T SHIP"
        print(f"\n  {red(bold('DOESN\'T SHIP ✗'))}  Too many failures. This PR is not ready.")

    print("=" * 68)
    return score, verdict


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — ACCOUNTABILITY GATE
# ══════════════════════════════════════════════════════════════════════════════

def accountability_gate(score: int, verdict: str) -> str:
    """Ask the student one judgment question before saving the final scorecard."""
    print(f"\n→ Your team scored {score}/5. Verdict: {verdict}.")
    print()
    try:
        answer = input(
            "→ What is the ONE thing you would fix first before showing this to your tech lead? "
            "(1 sentence): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if not answer:
        student_judgment = "NOT ANSWERED"
        print("  (No answer recorded — shown in trainer review)")
    else:
        student_judgment = answer
        print("  Judgment recorded.")

    return student_judgment


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — SAVE SCORECARD
# ══════════════════════════════════════════════════════════════════════════════

def save_scorecard(checks: list, score: int, verdict: str, student_judgment: str):
    scorecard = {
        "sprint": "Sprint 6 — Competitive Build",
        "generated_at": datetime.now().isoformat(),
        "challenge_pipeline": CHALLENGE_PATH,
        "score": score,
        "max_score": 5,
        "verdict": verdict,
        "student_judgment": student_judgment,
        "checks": {
            "code_review":    checks[0],
            "documentation":  checks[1],
            "testing":        checks[2],
            "ci_slo":         checks[3],
            "observability":  checks[4],
        },
    }
    out_path = os.path.join(COMPETITIVE_DIR, "competitive_scorecard.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scorecard, f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 68)
    print(bold("DAY 8 — SPRINT 6: COMPETITIVE BUILD"))
    print("Challenge pipeline: challenge_pipeline.py")
    print("Model: Nova Lite only  |  Time limit: 60 minutes")
    print("=" * 68)
    print()

    # ── Step 1: Create challenge pipeline ─────────────────────────────────────
    create_challenge_pipeline()

    # ── Connect to Bedrock ─────────────────────────────────────────────────────
    try:
        client = boto3.client("bedrock-runtime", region_name=REGION)
    except Exception as e:
        print(f"[ERROR] Could not create Bedrock client: {e}")
        sys.exit(1)

    # ── Step 2: Run all five checks ────────────────────────────────────────────
    checks = []

    c1 = check_code_review(client)
    checks.append(c1)

    c2 = check_documentation(client)
    checks.append(c2)

    c3 = check_testing(client)
    checks.append(c3)

    c4 = check_ci_slo()
    checks.append(c4)

    c5 = check_observability(client, c1)
    checks.append(c5)

    # ── Step 3: Print scorecard ────────────────────────────────────────────────
    score, verdict = print_scorecard(checks)

    # ── Step 4: Accountability gate ────────────────────────────────────────────
    student_judgment = accountability_gate(score, verdict)

    # ── Step 5: Save everything ────────────────────────────────────────────────
    save_scorecard(checks, score, verdict, student_judgment)

    print()
    print("Output files:")
    print(f"  labs/competitive_build/challenge_pipeline.py")
    print(f"  labs/output/code_review.json")
    print(f"  labs/output/test_results.json")
    print(f"  labs/output/slo_priority.json")
    print(f"  labs/output/competitive_scorecard.json  ← tracked by Vercel dashboard")
    print()
    print("Sprint 6 complete.  Wait for Anil's verdict.")


if __name__ == "__main__":
    main()
