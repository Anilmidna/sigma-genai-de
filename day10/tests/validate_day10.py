"""
Day 10 — Validation Script
Run this to confirm your environment is ready, and to validate your lab outputs.
Usage: python tests/validate_day10.py
"""

import sys
import os
import json
import re
import sqlite3

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab")
DUCKDB_PATH = os.path.join(LAB_DIR, "sigma_platform.duckdb")
OUTPUT_DIR = os.path.join(LAB_DIR, "agent_outputs")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

results = {"pass": 0, "fail": 0, "skip": 0}
judgment_answers = []

def check(test_name: str, condition: bool, hint: str = ""):
    if condition:
        print(f"  [{PASS}] {test_name}")
        results["pass"] += 1
    else:
        print(f"  [{FAIL}] {test_name}")
        if hint:
            print(f"         → {hint}")
        results["fail"] += 1

def skip(test_name: str, reason: str):
    print(f"  [{SKIP}] {test_name} — {reason}")
    results["skip"] += 1

def check_judgment(report_path: str, lab_label: str):
    """Check if student answered the accountability gate question."""
    if not os.path.exists(report_path):
        return
    try:
        with open(report_path, encoding="utf-8") as f:
            data = json.load(f)
        answer = data.get("student_judgment", "NOT ANSWERED")
        answered = answer and answer != "NOT ANSWERED" and len(answer.strip()) > 5
        check(f"{lab_label}: student judgment answered",
              answered,
              f'Currently: "{answer[:80]}" — answer the question when prompted at the end of the script')
        if answered:
            judgment_answers.append((lab_label, answer[:120]))
    except (json.JSONDecodeError, Exception):
        pass

print("\n" + "="*60)
print("DAY 10 — ENVIRONMENT PREFLIGHT CHECK")
print("="*60 + "\n")

preflight_results = []
def preflight_check(name, ok, detail=""):
    icon = "  ✅" if ok else "  ❌"
    msg = f"{icon} {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    preflight_results.append(ok)

# 1. Python version
py_ok = sys.version_info >= (3, 10)
preflight_check("Python 3.10+", py_ok, f"found {sys.version.split()[0]}")

# 2. Required packages
packages = {
    "boto3":          "boto3",
    "duckdb":         "duckdb",
    "langgraph":      "langgraph",
    "langchain_core": "langchain-core",
    "crewai":         "crewai",
    "litellm":        "litellm",
}
for import_name, pip_name in packages.items():
    try:
        __import__(import_name)
        preflight_check(f"Package: {pip_name}", True)
    except ImportError:
        preflight_check(f"Package: {pip_name}", False, f"run: pip install {pip_name}")

# 3. AWS credentials
try:
    import boto3
    sts = boto3.client("sts", region_name="us-east-1")
    identity = sts.get_caller_identity()
    account = identity.get("Account", "unknown")
    preflight_check("AWS credentials", True, f"account {account}")
except Exception as e:
    preflight_check("AWS credentials", False, f"{e}")

# 4. Bedrock access (Nova Pro)
try:
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = bedrock.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Reply with: OK"}]}],
            "inferenceConfig": {"maxTokens": 10},
        }),
    )
    reply = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]
    preflight_check("Bedrock Nova Pro", True, f'model replied: "{reply.strip()[:30]}"')
except Exception as e:
    preflight_check("Bedrock Nova Pro", False, str(e)[:80])

# 5. Bedrock access (Nova Lite)
try:
    resp = bedrock.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Reply with: OK"}]}],
            "inferenceConfig": {"maxTokens": 10},
        }),
    )
    reply = json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]
    preflight_check("Bedrock Nova Lite", True, f'model replied: "{reply.strip()[:30]}"')
except Exception as e:
    preflight_check("Bedrock Nova Lite", False, str(e)[:80])

# 6. DuckDB file
db_ok = os.path.exists(DUCKDB_PATH)
preflight_check("sigma_platform.duckdb present", db_ok, DUCKDB_PATH if not db_ok else "")

if db_ok:
    try:
        import duckdb
        conn = duckdb.connect(DUCKDB_PATH, read_only=True)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        conn.close()
        preflight_check("DuckDB readable", True, f"tables: {', '.join(tables)}")
    except Exception as e:
        preflight_check("DuckDB readable", False, str(e)[:80])

print("\n" + "="*60)
passed_preflight = sum(preflight_results)
total_preflight  = len(preflight_results)
print(f"PREFLIGHT: {passed_preflight}/{total_preflight} checks passed")
print("="*60)

if passed_preflight < total_preflight:
    print(f"\n{FAIL} Fix preflight environment checks before running post-lab validations.\n")
    sys.exit(1)

# ──────────────────────────────────────────────────────────────────────────────
# POST-LAB VALIDATIONS
# ──────────────────────────────────────────────────────────────────────────────

# ── LAB 1: Raw ReAct Agent ────────────────────────────────────────────────────
print("\n── LAB 1: Build Your Own ReAct Agent ────────────────────────────────")

react_trace = os.path.join(OUTPUT_DIR, "react_trace.json")
react_answer = os.path.join(OUTPUT_DIR, "react_answer.txt")
flagged_merchants = os.path.join(OUTPUT_DIR, "flagged_merchants.json")
react_agent_py = os.path.join(LAB_DIR, "1_react_agent.py")

check("1_react_agent.py exists", os.path.exists(react_agent_py))

# Check if flag_merchant is registered in TOOLS
registered = False
if os.path.exists(react_agent_py):
    with open(react_agent_py, "r", encoding="utf-8", errors="replace") as f:
        code_content = f.read()
    # Find active lines of registering tool
    match = re.search(r'TOOLS\["flag_merchant"\]\s*=\s*tool_flag_merchant', code_content)
    # Check if the line is not commented out
    if match:
        start_idx = match.start()
        # Look backwards to check if there is a '#' in the same line
        line_start = code_content.rfind('\n', 0, start_idx) + 1
        line_str = code_content[line_start:start_idx]
        if "#" not in line_str:
            registered = True
            
check("flag_merchant tool registered in TOOLS", registered, "Ensure you register the tool: TOOLS['flag_merchant'] = tool_flag_merchant")

# Check output files
check("agent_outputs/react_trace.json exists", os.path.exists(react_trace), "Run: cd lab && python 1_react_agent.py")
check("agent_outputs/react_answer.txt exists", os.path.exists(react_answer), "Run: cd lab && python 1_react_agent.py")

# Check flagged_merchants.json
if not os.path.exists(flagged_merchants):
    check("agent_outputs/flagged_merchants.json exists", False, "Implement tool_flag_merchant and uncomment Step 4 to run the flagging question")
else:
    try:
        with open(flagged_merchants, encoding="utf-8") as f:
            flagged = json.load(f)
        is_list = isinstance(flagged, list)
        check("flagged_merchants.json contains a JSON list", is_list)
        if is_list:
            check("flagged_merchants.json contains at least 1 entry", len(flagged) >= 1)
            valid_keys = all(isinstance(entry, dict) and "merchant_id" in entry and "reason" in entry and "flagged_at" in entry for entry in flagged)
            check("flagged_merchants.json entries have correct keys (merchant_id, reason, flagged_at)", valid_keys)
    except json.JSONDecodeError:
        check("flagged_merchants.json is valid JSON", False, "Cannot parse file")

# Verify agent called the tool in the run trace
if os.path.exists(react_trace):
    try:
        with open(react_trace, encoding="utf-8") as f:
            trace_data = json.load(f)
        
        called_tool = False
        trace_list = trace_data.get("trace", [])
        for step in trace_list:
            if step.get("action") == "flag_merchant":
                called_tool = True
                break
        check("react_trace.json shows agent executed 'flag_merchant'", called_tool, "Check if flag_merchant description is added to TOOL_DESCRIPTIONS")
        check_judgment(react_trace, "Lab 1")
    except Exception:
        pass

# ── LAB 2: LangGraph SQL Agent ────────────────────────────────────────────────
print("\n── LAB 2: LangGraph SQL Agent ───────────────────────────────────────")

lg_trace = os.path.join(OUTPUT_DIR, "langgraph_trace.json")
approved_queries = os.path.join(OUTPUT_DIR, "approved_queries.json")
agent_memory = os.path.join(LAB_DIR, "agent_memory.db")

check("agent_outputs/langgraph_trace.json exists", os.path.exists(lg_trace), "Run: cd lab && python 2_langgraph_sql_agent.py")
check("agent_outputs/approved_queries.json exists", os.path.exists(approved_queries), "Run: cd lab && python 2_langgraph_sql_agent.py")
check("agent_memory.db exists", os.path.exists(agent_memory), "Run: cd lab && python 2_langgraph_sql_agent.py")

if os.path.exists(agent_memory):
    try:
        conn = sqlite3.connect(agent_memory)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM query_history")
        rows = cursor.fetchone()[0]
        conn.close()
        check("agent_memory.db contains history records", rows > 0, f"Found {rows} queries in history")
    except Exception as e:
        check("agent_memory.db is readable", False, str(e))

check_judgment(lg_trace, "Lab 2")

# ── LAB 3: CrewAI DQ Team ─────────────────────────────────────────────────────
print("\n── LAB 3: CrewAI DQ Team ────────────────────────────────────────────")

crew_report = os.path.join(OUTPUT_DIR, "crewai_dq_report.json")
crew_sql = os.path.join(OUTPUT_DIR, "crewai_fix_queries.sql")

check("agent_outputs/crewai_dq_report.json exists", os.path.exists(crew_report), "Run: cd lab && python 3_crewai_de_team.py")
check("agent_outputs/crewai_fix_queries.sql exists", os.path.exists(crew_sql), "Run: cd lab && python 3_crewai_de_team.py")

check_judgment(crew_report, "Lab 3")

# ── LAB 4: Self-Healing Pipeline Agent ────────────────────────────────────────
print("\n── LAB 4: Self-Healing Pipeline Agent (Stretch) ─────────────────────")

healing_log = os.path.join(OUTPUT_DIR, "healing_log.json")
patched_pipeline = os.path.join(OUTPUT_DIR, "patched_pipeline.py")

if not os.path.exists(healing_log) and not os.path.exists(patched_pipeline):
    skip("Self-healing files missing", "Optional stretch goal. Run: cd lab && python 4_stretch_goal_agent_memory.py")
else:
    check("agent_outputs/healing_log.json exists", os.path.exists(healing_log))
    check("agent_outputs/patched_pipeline.py exists", os.path.exists(patched_pipeline))
    
    if os.path.exists(healing_log):
        try:
            with open(healing_log, encoding="utf-8") as f:
                log_data = json.load(f)
            check("healing_log.json is a valid list/dict", isinstance(log_data, (list, dict)))
        except json.JSONDecodeError:
            check("healing_log.json is valid JSON", False)
            
    check_judgment(healing_log, "Lab 4")

# ── JUDGMENT SUMMARY ──────────────────────────────────────────────────────────
if judgment_answers:
    print("\n── YOUR ANSWERS (saved to GitHub) ───────────────────────────────────")
    for lab, answer in judgment_answers:
        print(f"  {lab}: {answer}")

# ── FINAL REPORT ──────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
total_tests = results["pass"] + results["fail"]
print(f"RESULTS: {results['pass']}/{total_tests} passed  |  {results['fail']} failed  |  {results['skip']} skipped")
print("=" * 60)

if results["fail"] == 0 and results["pass"] >= 10:
    print("\n  ✅ ALL CORE LAB TESTS PASSED! Push your code to Vercel/GitHub dashboard:")
    print("  git add .")
    print('  git commit -m "Day 10 done — ReAct + LangGraph + CrewAI"')
    print("  git push\n")
elif results["fail"] == 0:
    print("\n  LOOKING GOOD. Run remaining scripts to complete all labs.\n")
else:
    print(f"\n  ❌ {results['fail']} tests need fixing. Please complete your build tasks.")
    print("  Run validator again: python tests/validate_day10.py\n")
