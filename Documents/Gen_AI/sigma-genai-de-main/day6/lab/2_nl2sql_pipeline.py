"""
NL2SQL Pipeline — Day 6, Module 2
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  Product and marketing raise 30-40 data requests per week.
  Average turnaround: 3 days. Sigma DataTech wants them to type
  English, get SQL, see results — in under 30 seconds.
  A basic LLM approach worked 60% of the time. Push it above 90%.

WHY THIS MATTERS (vs just asking ChatGPT "write me SQL"):
  - Schema-grounded → knows YOUR tables, columns, business rules
  - Safety validated → blocks DROP/DELETE before execution
  - Audited → every question/SQL/result logged for compliance
  - Executable → actually runs on Snowflake, returns real data
  - Explainable → translates results into friendly English

WHERE THIS FITS IN THE PLATFORM:
  Today: standalone NL2SQL pipeline
  Day 6 Bonus: compare against Snowflake Cortex Analyst (same queries)
  Day 12: becomes the NL analytics interface with multi-turn memory

  IMPORTANT: SPEND 5 MINS TO REVIEW THE CODE. YOU HAVE A QUIZ ON THIS LATER. 
═══════════════════════════════════════════════════════════════

HOW TO RUN:
  python 2_nl2sql_pipeline.py
"""

import boto3
import json
import os
import re
from datetime import datetime
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from sample_data import SCHEMA_RICH, NL2SQL_QUESTIONS, SNOWFLAKE_CONFIG_TEMPLATE

# ── CONFIGURATION ──────────────────────────────────────────
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
MODEL_ID = 'amazon.nova-pro-v1:0'  # Pro for better SQL reasoning

# Schema context with business rules and few-shot examples
SCHEMA_CONTEXT = SCHEMA_RICH


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.1 — SQL GENERATOR
# ══════════════════════════════════════════════════════════════

def extract_sql(response_text: str) -> str:
    """Extract clean SQL from Nova's response (handles markdown fences)."""
    # Pattern 1: ```sql ... ```
    match = re.search(r"```sql\s*(.*?)\s*```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Pattern 2: ``` ... ```
    match = re.search(r"```\s*(SELECT.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Pattern 3: starts with SELECT
    if response_text.strip().upper().startswith("SELECT"):
        return response_text.strip()
    return None


def generate_sql(question: str) -> dict:
    """Send business question to Nova Pro with full schema context. Returns SQL."""
    print(f"\n[Nova Pro] Generating SQL for: '{question}'")

    system_prompt = f"""You are a senior Snowflake SQL expert for Sigma DataTech.
Convert business questions into correct Snowflake SQL.

{SCHEMA_CONTEXT}

INSTRUCTIONS:
1. Follow business rules EXACTLY.
2. Return in this format:
   EXPLANATION: (one sentence)
   ```sql
   (your SQL)
   ```
3. Use uppercase for SQL keywords and table/column names.
4. Always add meaningful column aliases."""

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": f"Question: {question}"}]}],
        inferenceConfig={"temperature": 0.1, "maxTokens": 800},
    )

    raw_text = response["output"]["message"]["content"][0]["text"]
    tokens_in = response["usage"]["inputTokens"]
    tokens_out = response["usage"]["outputTokens"]

    # Extract explanation
    explanation = ""
    for line in raw_text.split("\n"):
        if line.strip().startswith("EXPLANATION:"):
            explanation = line.replace("EXPLANATION:", "").strip()
            break

    sql = extract_sql(raw_text)
    print(f"[Nova Pro] Explanation: {explanation}")
    print(f"[Nova Pro] SQL:\n{sql}")
    print(f"[Nova Pro] Tokens: {tokens_in} in / {tokens_out} out")

    return {"question": question, "sql": sql, "explanation": explanation}


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.2 — SQL VALIDATOR
# ══════════════════════════════════════════════════════════════

def validate_sql(sql: str) -> tuple:
    """
    Safety check before executing AI-generated SQL.
    Returns (is_valid: bool, reason: str)

    Why? An LLM could generate DROP TABLE or INSERT statements.
    In production, this is non-negotiable.
    """
    if not sql:
        return False, "No SQL was generated"

    sql_upper = sql.upper().strip()

    # Only allow SELECT
    if not sql_upper.startswith("SELECT"):
        return False, f"Rejected: must start with SELECT, got: {sql[:30]}"

    # Block dangerous keywords
    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER", "CREATE"]
    for kw in dangerous:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False, f"Rejected: contains forbidden keyword: {kw}"

    # Must reference at least one known table
    known_tables = ["FACT_TRANSACTIONS", "DIM_MERCHANT"]
    if not any(t in sql_upper for t in known_tables):
        return False, "Rejected: no known Sigma DataTech table referenced"

    return True, "Validation passed"


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.3 — EXECUTOR + FULL PIPELINE
# ══════════════════════════════════════════════════════════════

try:
    import snowflake.connector
    SNOWFLAKE_AVAILABLE = True
except ImportError:
    SNOWFLAKE_AVAILABLE = False

SNOWFLAKE_CONFIG = SNOWFLAKE_CONFIG_TEMPLATE.copy()


def execute_sql(sql: str) -> dict:
    """Execute validated SQL on Snowflake. Returns results or error."""
    if not SNOWFLAKE_AVAILABLE:
        return {"rows": [], "columns": [], "row_count": 0,
                "error": "snowflake-connector not installed — SQL generated but not executed"}

    if SNOWFLAKE_CONFIG.get("account") == "YOUR_ACCOUNT_ID":
        print("[Snowflake] SKIPPED — credentials not configured in sample_data.py")
        return {"rows": [], "columns": [], "row_count": 0,
                "error": "Snowflake credentials not configured — edit SNOWFLAKE_CONFIG_TEMPLATE in sample_data.py"}

    print(f"[Snowflake] Executing...")
    try:
        cfg = SNOWFLAKE_CONFIG.copy()
        key_path = cfg.pop("private_key_path", None)
        if key_path:
            abs_key_path = os.path.join(os.path.dirname(__file__), key_path)
            with open(abs_key_path, 'rb') as f:
                private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())
            cfg["private_key"] = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        conn = snowflake.connector.connect(**cfg)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        print(f"[Snowflake] Returned {len(rows)} rows")
        return {"rows": rows, "columns": columns, "row_count": len(rows), "error": None}
    except Exception as e:
        print(f"[Snowflake] ERROR: {e}")
        return {"rows": [], "columns": [], "row_count": 0, "error": str(e)}
    finally:
        if 'cursor' in dir():
            cursor.close()
        if 'conn' in dir():
            conn.close()


def format_results(columns: list, rows: list) -> str:
    """Format query results as readable text table."""
    if not rows:
        return "No results returned."
    header = " | ".join(columns)
    sep = "-" * len(header)
    data = [" | ".join(str(v) for v in row) for row in rows[:20]]
    return "\n".join([header, sep] + data)


# ── AUDIT LOG ──────────────────────────────────────────────
AUDIT_LOG = []


def nl2sql(question: str) -> str:
    """
    Complete pipeline: Question → Generate SQL → Validate → Execute → Answer
    """
    print(f"\n{'=' * 60}")
    print(f"QUESTION: {question}")
    print(f"{'=' * 60}")

    # Step 1: Generate SQL
    gen = generate_sql(question)
    sql = gen["sql"]

    # Step 2: Validate
    is_valid, reason = validate_sql(sql)
    print(f"[Validator] {reason}")
    if not is_valid:
        AUDIT_LOG.append({"question": question, "sql": sql, "status": "REJECTED", "reason": reason})
        return f"Could not process: {reason}"

    # Step 3: Execute
    result = execute_sql(sql)
    if result["error"]:
        AUDIT_LOG.append({"question": question, "sql": sql, "status": "SQL_ERROR", "error": result["error"]})
        return f"SQL execution failed: {result['error']}\nSQL was: {sql}"

    # Step 4: Format results
    formatted = format_results(result["columns"], result["rows"])

    # Step 5: Generate friendly answer
    answer_response = bedrock.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": (
            f"User asked: {question}\n\n"
            f"SQL run:\n{sql}\n\n"
            f"Results:\n{formatted}\n\n"
            f"Summarise in 2-3 friendly sentences for a non-technical person. "
            f"Include the key numbers. Don't mention SQL or tables."
        )}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0.3},
    )
    answer = answer_response["output"]["message"]["content"][0]["text"]

    # Step 6: Audit log
    AUDIT_LOG.append({
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "sql": sql,
        "row_count": result["row_count"],
        "status": "SUCCESS",
    })

    print(f"\nANSWER: {answer}")
    return answer


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.4 — CONTEXT ABLATION EXPERIMENT
# Remove context → watch accuracy drop → proves why each piece matters
# ══════════════════════════════════════════════════════════════

def test_without_context(question: str, text_to_remove: str, label: str):
    """Temporarily remove schema context and test accuracy."""
    global SCHEMA_CONTEXT
    original = SCHEMA_CONTEXT

    SCHEMA_CONTEXT = SCHEMA_CONTEXT.replace(text_to_remove, "")

    print(f"\n{'!' * 60}")
    print(f"EXPERIMENT: Removed '{label}'")
    print(f"Question: {question}")
    result = generate_sql(question)
    print(f"SQL generated: {result['sql']}")
    print(f"{'!' * 60}")

    SCHEMA_CONTEXT = original  # Restore
    return result


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # --- Run the full pipeline with 5 questions ---
    print("\n" + "=" * 60)
    print("NL2SQL PIPELINE — RUNNING 5 TEST QUESTIONS")
    print("=" * 60)

    nl2sql("DROP TABLE fact_transactions")

    for q in NL2SQL_QUESTIONS:
        nl2sql(q)

    # --- Print audit log ---
    print(f"\n{'=' * 60}")
    print("AUDIT LOG")
    print(f"{'=' * 60}")
    for entry in AUDIT_LOG:
        status = entry.get("status", "?")
        print(f"[{status}] {entry.get('question', '')[:50]}")

    # --- Save audit log ---
    with open("nl2sql_audit.json", "w") as f:
        json.dump(AUDIT_LOG, f, indent=2)
    print(f"\nAudit log saved: nl2sql_audit.json ({len(AUDIT_LOG)} entries)")

    # --- Context ablation experiments ---
    print("\n\n" + "=" * 60)
    print("CONTEXT ABLATION EXPERIMENTS")
    print("=" * 60)

    test_without_context(
        "What is the net settled amount excluding held transactions?",
        "RULE 1: Revenue = SUM(AMOUNT) WHERE STATUS = 'COMPLETED' only.\n        FAILED and PENDING are NOT revenue.",
        "Revenue business rule"
    )

    test_without_context(
        "Which merchant had the most transactions?",
        "FACT_TRANSACTIONS.MERCHANT_ID = DIM_MERCHANT.MERCHANT_ID (MANY-TO-ONE)",
        "JOIN relationship hint"
    )

    test_without_context(
        "Show failure rate by payment method",
        "=== FEW-SHOT EXAMPLES (style guide) ===",
        "Few-shot examples"
    )
