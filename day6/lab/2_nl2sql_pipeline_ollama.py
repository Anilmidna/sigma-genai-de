"""
NL2SQL Pipeline (Ollama) — Day 6, Module 2 Variant
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
PURPOSE:
  This is the Ollama variant of 2_nl2sql_pipeline.py.
  Run BOTH files and compare SQL quality side by side.

  Bedrock Nova Pro  → production-grade, schema-aware, consistent
  Ollama qwen2.5:7b → local, free, but weaker on complex SQL

  The context ablation experiments are the same — watch how
  a smaller local model degrades when context is stripped vs
  how Nova Pro degrades. The difference proves why model choice
  matters for production NL2SQL.

HOW TO RUN:
  ollama serve          (in a separate terminal, if not running)
  python 2_nl2sql_pipeline_ollama.py
═══════════════════════════════════════════════════════════════
"""

import ollama
import json
import re
from datetime import datetime
from sample_data import SCHEMA_RICH, NL2SQL_QUESTIONS

# ── CONFIGURATION ──────────────────────────────────────────
MODEL_ID = 'qwen2.5:7b'

SCHEMA_CONTEXT = SCHEMA_RICH


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.1 — SQL GENERATOR
# ══════════════════════════════════════════════════════════════

def extract_sql(response_text: str) -> str:
    """Extract clean SQL from model response (handles markdown fences)."""
    match = re.search(r"```sql\s*(.*?)\s*```", response_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(SELECT.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if response_text.strip().upper().startswith("SELECT"):
        return response_text.strip()
    return None


def generate_sql(question: str) -> dict:
    """Send business question to Ollama with full schema context. Returns SQL."""
    print(f"\n[Ollama {MODEL_ID}] Generating SQL for: '{question}'")

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

    response = ollama.chat(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": f"Question: {question}"}
        ]
    )

    raw_text = response['message']['content']

    explanation = ""
    for line in raw_text.split("\n"):
        if line.strip().startswith("EXPLANATION:"):
            explanation = line.replace("EXPLANATION:", "").strip()
            break

    sql = extract_sql(raw_text)
    print(f"[Ollama] Explanation: {explanation}")
    print(f"[Ollama] SQL:\n{sql}")

    return {"question": question, "sql": sql, "explanation": explanation}


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.2 — SQL VALIDATOR (identical to Bedrock version)
# ══════════════════════════════════════════════════════════════

def validate_sql(sql: str) -> tuple:
    """Safety check before executing AI-generated SQL."""
    if not sql:
        return False, "No SQL was generated"

    sql_upper = sql.upper().strip()

    if not sql_upper.startswith("SELECT"):
        return False, f"Rejected: must start with SELECT, got: {sql[:30]}"

    dangerous = ["DROP", "DELETE", "INSERT", "UPDATE", "TRUNCATE", "ALTER", "CREATE"]
    for kw in dangerous:
        if re.search(rf'\b{kw}\b', sql_upper):
            return False, f"Rejected: contains forbidden keyword: {kw}"

    known_tables = ["FACT_TRANSACTIONS", "DIM_MERCHANT"]
    if not any(t in sql_upper for t in known_tables):
        return False, "Rejected: no known Sigma DataTech table referenced"

    return True, "Validation passed"


# ── AUDIT LOG ──────────────────────────────────────────────
AUDIT_LOG = []


def nl2sql(question: str) -> str:
    """Complete pipeline: Question → Generate SQL → Validate → (skip execution) → Answer"""
    print(f"\n{'=' * 60}")
    print(f"QUESTION: {question}")
    print(f"{'=' * 60}")

    gen = generate_sql(question)
    sql = gen["sql"]

    is_valid, reason = validate_sql(sql)
    print(f"[Validator] {reason}")
    if not is_valid:
        AUDIT_LOG.append({"question": question, "sql": sql, "status": "REJECTED", "reason": reason})
        return f"Could not process: {reason}"

    # Snowflake execution skipped in Ollama variant — focus is SQL quality comparison
    print("[Snowflake] SKIPPED in Ollama variant — SQL quality comparison only")

    summary_response = ollama.chat(
        model=MODEL_ID,
        messages=[{"role": "user", "content": (
            f"User asked: {question}\n\n"
            f"SQL generated:\n{sql}\n\n"
            f"Summarise in 2-3 friendly sentences what this SQL does "
            f"for a non-technical person. Don't mention SQL or tables."
        )}]
    )
    answer = summary_response['message']['content']

    AUDIT_LOG.append({
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "sql": sql,
        "status": "SQL_ONLY",
    })

    print(f"\nANSWER: {answer}")
    return answer


# ══════════════════════════════════════════════════════════════
# MILESTONE 2.4 — CONTEXT ABLATION EXPERIMENT
# Same experiments as Bedrock version — compare degradation patterns
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

    SCHEMA_CONTEXT = original
    return result


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(f"NL2SQL PIPELINE — OLLAMA ({MODEL_ID})")
    print("=" * 60)

    nl2sql("DROP TABLE fact_transactions")

    for q in NL2SQL_QUESTIONS:
        nl2sql(q)

    print(f"\n{'=' * 60}")
    print("AUDIT LOG")
    print(f"{'=' * 60}")
    for entry in AUDIT_LOG:
        status = entry.get("status", "?")
        print(f"[{status}] {entry.get('question', '')[:50]}")

    with open("nl2sql_audit_ollama.json", "w") as f:
        json.dump(AUDIT_LOG, f, indent=2)
    print(f"\nAudit log saved: nl2sql_audit_ollama.json ({len(AUDIT_LOG)} entries)")

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
