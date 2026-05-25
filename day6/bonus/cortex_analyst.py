import json
import time
import os
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ── CONFIGURATION ──────────────────────────────────────────
ACCOUNT = 'GEJKIOG-TKC55632'
USER = 'student_genai'
KEY_FILE = os.path.join(os.path.dirname(__file__), 'student_key.p8')

# Load private key
with open(KEY_FILE, 'rb') as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

PRIVATE_KEY_BYTES = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Semantic model path in Snowflake stage
SEMANTIC_MODEL = '@SIGMA_DE.PUBLIC.SEMANTIC_MODELS/sigma_semantic_model.yaml'


def get_connection():
    """Connect to Snowflake using key-pair auth."""
    return snowflake.connector.connect(
        user=USER,
        account=ACCOUNT,
        private_key=PRIVATE_KEY_BYTES,
        database='SIGMA_DE',
        schema='PUBLIC',
        warehouse='COMPUTE_WH',
        role='STUDENT_CORTEX'
    )


# ── CORTEX ANALYST QUERY ──────────────────────────────────

def ask_cortex(question: str) -> dict:
    """
    Ask Cortex Analyst a question via SQL.
    Cortex generates SQL from the semantic model and returns results.
    """
    print(f"\n[Cortex] Sending question: '{question}'")
    start_time = time.time()

    conn = get_connection()
    cur = conn.cursor()

    # Call Cortex COMPLETE with analyst instructions
    # This uses the semantic model to ground the response
    prompt = f"""You are a Snowflake SQL expert. Using the semantic model at {SEMANTIC_MODEL},
generate and execute SQL to answer this question: {question}

Return your answer in this exact format:
SQL: <the sql query you would run>
ANSWER: <friendly 1-2 sentence answer with the numbers>"""

    cur.execute(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', %s)", (prompt,))
    response_text = cur.fetchone()[0]
    elapsed = time.time() - start_time

    # Now generate the actual SQL and run it
    sql_prompt = f"""Given this schema:
- FACT_TRANSACTIONS(TRANSACTION_ID, AMOUNT, STATUS[COMPLETED/FAILED/PENDING], MERCHANT_ID, CUSTOMER_ID, TRANSACTION_DATE, PAYMENT_METHOD[CREDIT_CARD/DEBIT_CARD/UPI])
- DIM_MERCHANT(MERCHANT_ID, MERCHANT_NAME, CATEGORY, CITY)
- Revenue = SUM(AMOUNT) WHERE STATUS = 'COMPLETED' only

Write a Snowflake SQL query to answer: {question}
Return ONLY the SQL. No explanation."""

    cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', %s)", (sql_prompt,))
    sql_response = cur.fetchone()[0].strip()

    # Clean SQL from markdown fences if present
    if sql_response.startswith("```"):
        sql_response = sql_response.split("\n", 1)[1]
        sql_response = sql_response.rsplit("```", 1)[0].strip()

    print(f"[Cortex] Generated SQL:\n{sql_response}")

    # Execute the generated SQL
    result = {
        "sql": sql_response,
        "answer": None,
        "columns": [],
        "rows": [],
        "elapsed_seconds": elapsed,
        "error": None
    }

    try:
        cur.execute(sql_response)
        result["columns"] = [desc[0] for desc in cur.description]
        result["rows"] = cur.fetchall()
        print(f"[Cortex] Returned {len(result['rows'])} rows")
    except Exception as e:
        result["error"] = str(e)
        print(f"[Cortex] Execution error: {e}")

    conn.close()
    result["elapsed_seconds"] = time.time() - start_time
    return result


def display_results(question: str, result: dict):
    """Prints results in a readable format."""
    print(f"\n{'─'*60}")
    print(f"Q: {question}")
    print(f"{'─'*60}")

    if result.get("error"):
        print(f"ERROR: {result['error']}")
        return

    print(f"SQL Generated:\n{result['sql']}\n")

    if result["columns"]:
        header = " | ".join(result["columns"])
        print(header)
        print("-" * len(header))
        for row in result["rows"][:10]:
            print(" | ".join(str(v) for v in row))

    print(f"\nResponse time: {result['elapsed_seconds']:.2f}s")


## MILESTONE 4 — Run the Same 5 Questions from Module 2

# ── THE 5 COMPARISON QUESTIONS ──────────────────────────────
# These are the SAME questions from Module 2.
# We will compare Cortex Analyst vs our hand-built NL2SQL pipeline.

COMPARISON_QUESTIONS = [
    "How many transactions do we have in total?",
    "How many transactions failed?",
    "Which merchant had the highest revenue?",
    "What is the failure rate for each payment method?",
    "What was the total revenue generated across all merchants?"
]

# ── COMPARISON RUNNER ────────────────────────────────────────

def run_comparison():
    """
    Runs all 5 questions through Cortex Analyst and records results
    for comparison with Module 2's NL2SQL output.
    """
    print("\n" + "="*60)
    print("  CORTEX ANALYST — 5 QUESTION TEST")
    print("  Compare results against Module 2 NL2SQL output")
    print("="*60)

    comparison_log = []

    for i, question in enumerate(COMPARISON_QUESTIONS, 1):
        print(f"\n\n[Question {i}/5]")
        result = ask_cortex(question)
        display_results(question, result)

        comparison_log.append({
            "question_num": i,
            "question": question,
            "sql_generated": result.get("sql"),
            "answer": result.get("answer"),
            "row_count": len(result.get("rows", [])),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "error": result.get("error")
        })

        # Brief pause between questions to be polite to the API
        time.sleep(1)

    # Summary table
    print("\n\n" + "="*60)
    print("CORTEX ANALYST RESULTS SUMMARY")
    print("="*60)
    print(f"{'#':<3} {'Question':<45} {'Rows':<5} {'Time':<7} {'Status'}")
    print("-" * 70)
    for entry in comparison_log:
        status = "OK" if not entry["error"] else "ERROR"
        print(
            f"{entry['question_num']:<3} "
            f"{entry['question'][:44]:<45} "
            f"{entry['row_count']:<5} "
            f"{entry['elapsed_seconds']:.1f}s  "
            f"{status}"
        )

    # Save for Team Challenge comparison doc
    with open("cortex_results.json", "w") as f:
        json.dump(comparison_log, f, indent=2)
    print(f"\nResults saved to cortex_results.json")
    print("Use this file in your Team Challenge comparison document.")

    return comparison_log


if __name__ == "__main__":
    run_comparison()