"""
Day 10 — Preflight Validation Script
Run this BEFORE starting any lab to confirm your environment is ready.
Usage: python validate_day10.py
"""

import sys, os, json, subprocess

LAB_DIR = os.path.join(os.path.dirname(__file__), "..", "lab")
DUCKDB_PATH = os.path.join(LAB_DIR, "sigma_platform.duckdb")

PASS = "  ✅"
FAIL = "  ❌"
WARN = "  ⚠ "

results = []

def check(name, ok, detail=""):
    icon = PASS if ok else FAIL
    msg = f"{icon} {name}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    results.append(ok)

print("\n" + "="*60)
print("DAY 10 — ENVIRONMENT PREFLIGHT CHECK")
print("="*60 + "\n")

# ── Python version ────────────────────────────────────────────────────────────
py_ok = sys.version_info >= (3, 10)
check("Python 3.10+", py_ok, f"found {sys.version.split()[0]}")

# ── Required packages ─────────────────────────────────────────────────────────
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
        check(f"Package: {pip_name}", True)
    except ImportError:
        check(f"Package: {pip_name}", False, f"run: pip install {pip_name}")

# ── AWS credentials ───────────────────────────────────────────────────────────
try:
    import boto3
    sts = boto3.client("sts", region_name="us-east-1")
    identity = sts.get_caller_identity()
    account = identity.get("Account", "unknown")
    check("AWS credentials", True, f"account {account}")
except Exception as e:
    check("AWS credentials", False, f"{e}")

# ── Bedrock access (Nova Pro) ─────────────────────────────────────────────────
try:
    import boto3, json as _json
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = bedrock.invoke_model(
        modelId="amazon.nova-pro-v1:0",
        body=_json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Reply with: OK"}]}],
            "inferenceConfig": {"maxTokens": 10},
        }),
    )
    reply = _json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]
    check("Bedrock Nova Pro", True, f'model replied: "{reply.strip()[:30]}"')
except Exception as e:
    check("Bedrock Nova Pro", False, str(e)[:80])

# ── Bedrock access (Nova Lite) ────────────────────────────────────────────────
try:
    import boto3, json as _json
    bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = bedrock.invoke_model(
        modelId="amazon.nova-lite-v1:0",
        body=_json.dumps({
            "messages": [{"role": "user", "content": [{"text": "Reply with: OK"}]}],
            "inferenceConfig": {"maxTokens": 10},
        }),
    )
    reply = _json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]
    check("Bedrock Nova Lite", True, f'model replied: "{reply.strip()[:30]}"')
except Exception as e:
    check("Bedrock Nova Lite", False, str(e)[:80])

# ── DuckDB file ───────────────────────────────────────────────────────────────
db_ok = os.path.exists(DUCKDB_PATH)
check("sigma_platform.duckdb present", db_ok, DUCKDB_PATH if not db_ok else "")

if db_ok:
    try:
        import duckdb
        conn = duckdb.connect(DUCKDB_PATH, read_only=True)
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        conn.close()
        check("DuckDB readable", True, f"tables: {', '.join(tables)}")
    except Exception as e:
        check("DuckDB readable", False, str(e)[:80])

# ── agent_outputs dir ─────────────────────────────────────────────────────────
out_dir = os.path.join(LAB_DIR, "agent_outputs")
os.makedirs(out_dir, exist_ok=True)
check("agent_outputs/ directory", True, out_dir)

# ── LangGraph import check ────────────────────────────────────────────────────
try:
    from langgraph.graph import StateGraph, END
    check("LangGraph StateGraph import", True)
except Exception as e:
    check("LangGraph StateGraph import", False, str(e)[:80])

# ── CrewAI import check ───────────────────────────────────────────────────────
try:
    from crewai import Agent, Task, Crew, Process, LLM
    check("CrewAI core imports", True)
except Exception as e:
    check("CrewAI core imports", False, str(e)[:80])

# ── Summary ───────────────────────────────────────────────────────────────────
print()
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"{'='*60}")
    print(f"✅ ALL {total} CHECKS PASSED — You are ready for Day 10 labs!")
    print(f"{'='*60}\n")
else:
    failed = total - passed
    print(f"{'='*60}")
    print(f"⚠  {passed}/{total} checks passed. Fix the {failed} ❌ items above first.")
    print(f"{'='*60}\n")
    sys.exit(1)
