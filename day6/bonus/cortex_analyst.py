# ============================================================
# cortex_analyst.py
# Cortex Analyst Client — Sigma DataTech
# Day 6, Bonus Lab — GenAI for Data Engineering
# ============================================================
# STRETCH GOAL: Multi-turn conversational mode added.
# Uses conversation_history to pass prior Q&A context to each
# new Cortex COMPLETE call, enabling follow-up questions.
# ============================================================

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


# ── STRETCH GOAL: MULTI-TURN CONVERSATION ──────────────────
# conversation_history stores all Q&A turns so that each new
# ask_cortex_conversational() call has the full dialogue context.
# This mirrors the messages[] pattern used in chat APIs.

conversation_history: list[dict] = []


def clear_conversation():
    """Reset conversation history to start a fresh topic."""
    global conversation_history
    conversation_history = []
    print("[Conversation] History cleared. Starting fresh.")


def _build_context_prompt() -> str:
    """
    Serialise conversation_history into a readable context block
    that can be injected into the COMPLETE prompt.
    Each prior turn is represented as:
      User asked: <question>
      Cortex answered: <summary> (using merchant X / amount Y / etc.)
    """
    if not conversation_history:
        return ""

    lines = ["CONVERSATION HISTORY (use this for context in follow-up questions):"]
    for turn in conversation_history:
        role = turn["role"].upper()  # USER or ASSISTANT
        # Content is a list of content parts; extract the text parts
        text_parts = [
            part["text"]
            for part in turn["content"]
            if part.get("type") == "text"
        ]
        lines.append(f"  [{role}]: {' '.join(text_parts)}")

    lines.append("")
    return "\n".join(lines)


def ask_cortex_conversational(question: str) -> dict:
    """
    Multi-turn version of ask_cortex().

    Maintains conversation_history so follow-up questions like
    "How many of their transactions failed?" resolve "their" from
    the previous answer (e.g. the top-revenue merchant identified
    in the prior turn).

    Each call:
      1. Appends the user question to conversation_history.
      2. Builds a context block from all prior turns.
      3. Passes that context to CORTEX.COMPLETE for SQL generation.
      4. Executes the SQL and fetches results.
      5. Appends a summary of the answer back to conversation_history.
    """
    global conversation_history

    print(f"\n[Cortex Conversational] Question: '{question}'")
    print(f"[Cortex Conversational] Turns in history: {len(conversation_history)}")
    start_time = time.time()

    # ── Step 1: record the user turn ───────────────────────
    conversation_history.append({
        "role": "user",
        "content": [{"type": "text", "text": question}]
    })

    conn = get_connection()
    cur = conn.cursor()

    # ── Step 2: build the contextual SQL-generation prompt ─
    context_block = _build_context_prompt()

    sql_prompt = f"""You are a Snowflake SQL expert with access to this schema:
- FACT_TRANSACTIONS(TRANSACTION_ID, AMOUNT, STATUS[COMPLETED/FAILED/PENDING],
  MERCHANT_ID, CUSTOMER_ID, TRANSACTION_DATE,
  PAYMENT_METHOD[CREDIT_CARD/DEBIT_CARD/UPI])
- DIM_MERCHANT(MERCHANT_ID, MERCHANT_NAME, CATEGORY, CITY)
- Revenue = SUM(AMOUNT) WHERE STATUS = 'COMPLETED' only
- Semantic model: {SEMANTIC_MODEL}

{context_block}
CURRENT QUESTION: {question}

If the question refers to a specific merchant, payment method, or entity
mentioned in CONVERSATION HISTORY, use that entity in your SQL.

Return ONLY the SQL query with no markdown fences and no explanation."""

    cur.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', %s)", (sql_prompt,))
    sql_response = cur.fetchone()[0].strip()

    # ── Step 3: strip any accidental markdown fences ───────
    if sql_response.startswith("```"):
        sql_response = sql_response.split("\n", 1)[1]
        sql_response = sql_response.rsplit("```", 1)[0].strip()

    # Strip a leading "sql" token that some models emit
    if sql_response.lower().startswith("sql"):
        sql_response = sql_response[3:].lstrip()

    print(f"[Cortex Conversational] Generated SQL:\n{sql_response}")

    # ── Step 4: execute the SQL ─────────────────────────────
    result = {
        "sql": sql_response,
        "answer": None,
        "columns": [],
        "rows": [],
        "elapsed_seconds": 0.0,
        "error": None,
        "turn": len(conversation_history)  # which turn in the conversation
    }

    try:
        cur.execute(sql_response)
        result["columns"] = [desc[0] for desc in cur.description]
        result["rows"] = cur.fetchall()
        print(f"[Cortex Conversational] Returned {len(result['rows'])} rows")

        # ── Step 5: build a plain-text answer summary and
        #            record it as the assistant turn in history.
        #            This is what gives follow-up questions their context.
        if result["rows"]:
            # Produce a compact answer string: "Col1=val1, Col2=val2 | ..."
            answer_lines = []
            for row in result["rows"][:5]:  # cap at 5 rows in history
                pairs = ", ".join(
                    f"{col}={val}"
                    for col, val in zip(result["columns"], row)
                )
                answer_lines.append(pairs)
            answer_summary = " | ".join(answer_lines)
            result["answer"] = answer_summary
        else:
            answer_summary = "No rows returned."
            result["answer"] = answer_summary

        # Append assistant turn with the compact answer as context
        conversation_history.append({
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": (
                    f"SQL executed: {sql_response} | "
                    f"Result: {answer_summary}"
                )
            }]
        })

    except Exception as e:
        result["error"] = str(e)
        print(f"[Cortex Conversational] Execution error: {e}")
        # Still record the failed turn so history stays consistent
        conversation_history.append({
            "role": "assistant",
            "content": [{"type": "text", "text": f"Error executing SQL: {e}"}]
        })

    conn.close()
    result["elapsed_seconds"] = time.time() - start_time
    return result


def display_results_conversational(turn_num: int, question: str, result: dict):
    """Pretty-prints a single conversational turn."""
    print(f"\n{'═'*60}")
    print(f"  Turn {turn_num}: {question}")
    print(f"{'═'*60}")

    if result.get("error"):
        print(f"  ❌ ERROR: {result['error']}")
        return

    print(f"  SQL Generated:")
    for line in result['sql'].splitlines():
        print(f"    {line}")
    print()

    if result["columns"]:
        col_widths = [
            max(len(str(col)), max((len(str(row[i])) for row in result["rows"]), default=0))
            for i, col in enumerate(result["columns"])
        ]
        header = " | ".join(str(col).ljust(w) for col, w in zip(result["columns"], col_widths))
        print(f"  {header}")
        print(f"  {'-' * len(header)}")
        for row in result["rows"][:10]:
            print(f"  {' | '.join(str(v).ljust(w) for v, w in zip(row, col_widths))}")
        if len(result["rows"]) > 10:
            print(f"  ... ({len(result['rows'])} rows total, showing first 10)")

    print(f"\n  ⏱  Response time: {result['elapsed_seconds']:.2f}s")


# ── CONVERSATION DEMO ─────────────────────────────────────────
# Tests the three linked follow-up questions from the lab spec
# (cortex_analyst_lab.md, line 772-774) to demonstrate that
# Cortex remembers context across turns.

CONVERSATION_DEMO_QUESTIONS = [
    "Which merchant had the highest revenue?",
    "How many of their transactions failed?",        # ← 'their' = top merchant from turn 1
    "What payment method did those customers prefer?"  # ← 'those customers' from turns 1+2
]


def run_conversation_demo():
    """
    Runs the three linked follow-up questions from the stretch-goal spec.
    Each question builds on the answer of the previous one to show
    Cortex Analyst's contextual memory.
    """
    clear_conversation()

    print("\n" + "="*60)
    print("  CORTEX ANALYST — MULTI-TURN CONVERSATION DEMO")
    print("  Stretch Goal: Contextual follow-up questions")
    print("="*60)
    print("  Questions are chained — each follow-up relies on the")
    print("  answer from the previous turn.\n")

    conversation_log = []

    for i, question in enumerate(CONVERSATION_DEMO_QUESTIONS, 1):
        result = ask_cortex_conversational(question)
        display_results_conversational(i, question, result)

        conversation_log.append({
            "turn": i,
            "question": question,
            "sql_generated": result.get("sql"),
            "answer_summary": result.get("answer"),
            "row_count": len(result.get("rows", [])),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "error": result.get("error")
        })

        if i < len(CONVERSATION_DEMO_QUESTIONS):
            time.sleep(1)  # be polite to the API between turns

    # Summary
    print("\n\n" + "="*60)
    print("CONVERSATION DEMO SUMMARY")
    print("="*60)
    print(f"{'Turn':<5} {'Question':<45} {'Rows':<5} {'Time':<7} {'Status'}")
    print("-" * 70)
    for entry in conversation_log:
        status = "OK" if not entry["error"] else "ERROR"
        print(
            f"{entry['turn']:<5} "
            f"{entry['question'][:44]:<45} "
            f"{entry['row_count']:<5} "
            f"{entry['elapsed_seconds']:.1f}s  "
            f"{status}"
        )

    # Save conversation log
    with open("conversation_results.json", "w") as f:
        json.dump({
            "demo_questions": CONVERSATION_DEMO_QUESTIONS,
            "turns": conversation_log,
            "full_history": conversation_history
        }, f, indent=2)
    print("\nConversation log saved to conversation_results.json")
    return conversation_log


def run_interactive_chat():
    """
    Interactive REPL — type any question, type 'reset' to clear history,
    type 'quit' or 'exit' to stop.
    """
    clear_conversation()
    print("\n" + "="*60)
    print("  CORTEX ANALYST — INTERACTIVE CHAT")
    print("  Type your question. Commands: 'reset', 'history', 'quit'")
    print("="*60)

    turn = 0
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Chat] Exiting.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("[Chat] Goodbye!")
            break

        if user_input.lower() == "reset":
            clear_conversation()
            turn = 0
            continue

        if user_input.lower() == "history":
            if not conversation_history:
                print("  (No history yet)")
            else:
                print("\n── Conversation History ──")
                for h in conversation_history:
                    role = h["role"].upper()
                    texts = " ".join(p["text"] for p in h["content"] if p.get("type") == "text")
                    print(f"  [{role}]: {texts[:120]}")
            continue

        turn += 1
        result = ask_cortex_conversational(user_input)
        display_results_conversational(turn, user_input, result)


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "comparison"

    if mode == "chat":
        # python cortex_analyst.py chat
        run_interactive_chat()
    elif mode == "demo":
        # python cortex_analyst.py demo
        run_conversation_demo()
    else:
        # python cortex_analyst.py   (default — original batch comparison)
        run_comparison()
        print("\n" + "─"*60)
        print("TIP: Run with 'demo' to see multi-turn conversation stretch goal:")
        print("       python cortex_analyst.py demo")
        print("     Run with 'chat' for an interactive session:")
        print("       python cortex_analyst.py chat")