"""
==============================================================================
DAY 10 — LAB 1: BUILD YOUR OWN ReAct AGENT FROM SCRATCH
==============================================================================

MISSION BRIEFING
----------------
The Sigma DataTech fraud team has a question: "Which 3 merchants had the most
suspicious transaction patterns last month — high volume AND unusual amounts?"

A junior DE writes 3 separate queries and pastes results into a doc. You are
going to build an AI agent that answers multi-step questions autonomously.

BUT — you are building the loop yourself. No LangGraph. No LangChain.
Just Python, Bedrock, and DuckDB.

This is Lab 1 because the pain you feel building this manually is EXACTLY why
frameworks like LangGraph exist. You need to feel the problem before you get
the solution.

WHAT YOU WILL LEARN
-------------------
- The ReAct loop: Thought → Action → Observation → Repeat → Final Answer
- Why agents need tools (LLMs cannot query databases directly)
- How to parse structured actions from free-text LLM output
- Why runaway agents need iteration caps and why hallucination is dangerous
- The exact problem LangGraph solves (you build it in Lab 2)

MANUAL FIRST (3 minutes — close your laptop)
---------------------------------------------
On paper or whiteboard: write the steps you would take to answer:
"Which 3 merchants had the most suspicious transaction patterns last month?"

How many queries? What counts as suspicious? When do you stop?
Then run this script and compare your reasoning chain to the agent's.

WHERE THIS FITS
---------------
This agent has no memory, no state persistence, no retry logic, no parallel
tools. By the end of Lab 2 you will have all of those — built properly.
This is the "before" so you appreciate the "after."

==============================================================================
OUTPUT
------
  agent_outputs/react_trace.json   — full reasoning trace (Thought/Action/Obs)
  agent_outputs/react_answer.txt   — final answer
==============================================================================
"""

import os, sys, json, re, duckdb
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
MAX_ITER   = 6          # safety cap — agents can loop forever without this
DB_PATH    = os.path.join(os.path.dirname(__file__), "sigma_platform.duckdb")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "") -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 1500, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"]

# ── Tools the agent can call ──────────────────────────────────────────────────
def tool_query_db(sql: str) -> str:
    """Execute SQL against DuckDB and return results as a string."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        result = conn.execute(sql).fetchdf()
        conn.close()
        if result.empty:
            return "Query returned 0 rows."
        return result.to_string(index=False, max_rows=20)
    except Exception as e:
        return f"SQL ERROR: {e}"

def tool_get_schema() -> str:
    """Return the schema of available tables."""
    try:
        conn = duckdb.connect(DB_PATH, read_only=True)
        tables = conn.execute("SHOW TABLES").fetchall()
        schema_parts = []
        for (table,) in tables:
            cols = conn.execute(f"DESCRIBE {table}").fetchall()
            col_desc = ", ".join(f"{c[0]} {c[1]}" for c in cols)
            schema_parts.append(f"TABLE {table}: {col_desc}")
        conn.close()
        return "\n".join(schema_parts)
    except Exception as e:
        return f"SCHEMA ERROR: {e}"

def tool_calculate(expression: str) -> str:
    """Safely evaluate a simple numeric expression."""
    try:
        allowed = set("0123456789+-*/()., ")
        if not all(c in allowed for c in expression):
            return "ERROR: Only numeric expressions allowed."
        return str(eval(expression))  # noqa: S307 — filtered above
    except Exception as e:
        return f"CALC ERROR: {e}"

TOOLS = {
    "query_db":   tool_query_db,
    "get_schema": tool_get_schema,
    "calculate":  tool_calculate,
}

TOOL_DESCRIPTIONS = """
Available tools:
  query_db(sql)         — Run a SQL query against the Sigma DataTech database
  get_schema()          — Get table names and column definitions
  calculate(expression) — Evaluate a simple math expression (e.g. "12345 / 30")
"""

# ── ReAct system prompt ───────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a data engineering agent for Sigma DataTech.
You answer questions by reasoning step-by-step and using tools.

{TOOL_DESCRIPTIONS}

STRICT OUTPUT FORMAT — follow this exactly for every step:
Thought: [your reasoning about what to do next]
Action: tool_name
Input: the tool input (SQL query, expression, or empty string for get_schema)

When you have enough information to answer:
Thought: I now have the answer.
Final Answer: [your complete answer with specific numbers from the data]

Rules:
- NEVER make up data. Only use what tools return.
- If a query fails, fix the SQL and retry.
- Always call get_schema first if you are unsure about table structure.
- Maximum {MAX_ITER} steps then give your best answer.
"""

# ── Parse agent output ────────────────────────────────────────────────────────
def parse_agent_output(text: str) -> dict:
    """Extract Thought, Action, Input, or Final Answer from LLM output."""
    result = {"thought": "", "action": None, "input": "", "final_answer": None}

    if "Final Answer:" in text:
        result["final_answer"] = text.split("Final Answer:")[-1].strip()
        thought_match = re.search(r"Thought:(.*?)(?:Final Answer:)", text, re.DOTALL)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()
        return result

    thought_match = re.search(r"Thought:(.*?)(?:Action:|$)", text, re.DOTALL)
    action_match  = re.search(r"Action:\s*(\w+)", text)
    input_match   = re.search(r"Input:(.*?)(?:Thought:|Action:|$)", text, re.DOTALL)

    if thought_match:
        result["thought"] = thought_match.group(1).strip()
    if action_match:
        result["action"] = action_match.group(1).strip()
    if input_match:
        result["input"] = input_match.group(1).strip()

    return result

# ── The ReAct loop ────────────────────────────────────────────────────────────
def run_react_agent(question: str) -> dict:
    print(f"\n{'='*70}")
    print(f"AGENT QUESTION: {question}")
    print(f"{'='*70}\n")

    conversation = f"Question: {question}\n\n"
    trace = []

    for iteration in range(1, MAX_ITER + 1):
        print(f"--- Step {iteration} ---")

        response = call_bedrock(conversation, system=SYSTEM_PROMPT)
        parsed   = parse_agent_output(response)

        step = {
            "step":        iteration,
            "thought":     parsed["thought"],
            "action":      parsed["action"],
            "input":       parsed["input"],
            "observation": "",
            "final":       False,
        }

        print(f"Thought: {parsed['thought'][:200]}")

        # ── Final answer reached ──────────────────────────────────────────────
        if parsed["final_answer"]:
            step["final"]    = True
            step["thought"]  = parsed["thought"]
            step["answer"]   = parsed["final_answer"]
            trace.append(step)
            print(f"\n✅ FINAL ANSWER:\n{parsed['final_answer']}\n")
            return {"question": question, "trace": trace, "answer": parsed["final_answer"], "steps": iteration}

        # ── Execute tool ──────────────────────────────────────────────────────
        if parsed["action"] in TOOLS:
            tool_fn = TOOLS[parsed["action"]]
            tool_input = parsed["input"].strip('"\'')

            if parsed["action"] == "get_schema":
                observation = tool_fn()
            else:
                observation = tool_fn(tool_input)

            print(f"Action: {parsed['action']}")
            print(f"Input:  {tool_input[:100]}")
            print(f"Obs:    {str(observation)[:300]}\n")

            step["observation"] = str(observation)[:500]
            conversation += f"{response}\nObservation: {observation}\n\n"
        else:
            observation = f"Unknown tool '{parsed['action']}'. Available: {list(TOOLS.keys())}"
            print(f"⚠ {observation}\n")
            step["observation"] = observation
            conversation += f"{response}\nObservation: {observation}\n\n"

        trace.append(step)

    # ── Max iterations hit ────────────────────────────────────────────────────
    print(f"\n⚠ Max iterations ({MAX_ITER}) reached. Requesting best answer.")
    final_prompt = conversation + f"\nYou have reached the step limit. Based on everything above, give your best Final Answer now."
    final_resp = call_bedrock(final_prompt, system=SYSTEM_PROMPT)
    parsed = parse_agent_output(final_resp)
    answer = parsed.get("final_answer") or final_resp
    trace.append({"step": MAX_ITER + 1, "thought": "Max iterations — forced answer", "final": True, "answer": answer})
    return {"question": question, "trace": trace, "answer": answer, "steps": MAX_ITER}

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*70)
    print("DAY 10 — LAB 1: Raw ReAct Agent (no framework)")
    print("Sigma DataTech Fraud Investigation")
    print("="*70)

    question = (
        "Which 3 merchants had the most suspicious transaction patterns? "
        "Look for merchants with high transaction volume but also unusual average amounts "
        "(either very high or very low compared to others). Give me their names, "
        "transaction count, and average amount."
    )

    # ── PREDICT FIRST ─────────────────────────────────────────────────────────
    # Before the agent runs, you predict. This forces you to decompose the problem.
    print("\n" + "─"*60)
    print("PREDICT FIRST — answer before the agent runs")
    print("─"*60)
    print("Read the question above. You have 3 tools: query_db, get_schema, calculate.")
    print("To answer it, the agent must: check the schema, write SQL, maybe calculate.")
    print()
    print("Predict: how many Thought → Action → Observation cycles before Final Answer?")
    try:
        step_prediction = int(input("  Your prediction (1–6): ").strip())
    except (ValueError, EOFError):
        step_prediction = 0
    print(f"\n  Prediction locked: {step_prediction} steps. Starting agent...\n")

    result = run_react_agent(question)

    # ── PREDICTION VERDICT ────────────────────────────────────────────────────
    actual_steps = result["steps"]
    diff = abs(step_prediction - actual_steps)
    print(f"\n{'─'*60}")
    print(f"PREDICTION CHECK: you predicted {step_prediction}, agent took {actual_steps}")
    if step_prediction > 0 and diff == 0:
        print("  ✅ Exact match — you reasoned exactly like the agent.")
    elif step_prediction > 0 and diff <= 1:
        print("  ✅ Off by 1 — you understood the rough complexity.")
    elif step_prediction > 0:
        verdict = "underestimated" if step_prediction < actual_steps else "overestimated"
        print(f"  ⚠  You {verdict} by {diff} steps.")
        print("  Open react_trace.json → find the step that surprised you most.")
        try:
            miss = input("  In one line — which step was unexpected and why? ").strip()
        except EOFError:
            miss = ""
        result["prediction_miss_reason"] = miss or "NOT ANSWERED"
    result["step_prediction"] = step_prediction

    # Save trace
    trace_path = os.path.join(OUTPUT_DIR, "react_trace.json")
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    answer_path = os.path.join(OUTPUT_DIR, "react_answer.txt")
    with open(answer_path, "w", encoding="utf-8") as f:
        f.write(f"Question: {result['question']}\n\n")
        f.write(f"Steps taken: {result['steps']}\n\n")
        f.write(f"Answer:\n{result['answer']}\n")

    print(f"\n[SAVED] {trace_path}")
    print(f"[SAVED] {answer_path}")

    # ── Judgment question (accountability) ───────────────────────────────────
    print("\n" + "─"*60)
    print("JUDGMENT QUESTION (answer before continuing to Lab 2):")
    print("─"*60)
    print("The agent took", result["steps"], "steps to answer a question")
    print("you could answer with 2 SQL queries.")
    print()
    answer = input("In one sentence — when is an agent WORTH the extra complexity vs just writing the SQL yourself? ").strip()
    if not answer:
        answer = "NOT ANSWERED"

    result["student_judgment"] = answer
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("\n✅ Lab 1 complete. In Lab 2 you rebuild this — properly.")
    print("   LangGraph gives you: state, memory, retries, parallel tools,")
    print("   and conditional routing. You'll feel why in 60 minutes.")


# ═════════════════════════════════════════════════════════════════════════════
# STUDENT BUILD TASK — Add a 4th tool to the ReAct agent
# Time: 20–25 minutes  |  Mandatory before Lab 2
# ═════════════════════════════════════════════════════════════════════════════
#
# The agent you just ran has 3 tools: query_db, get_schema, calculate.
# Tools are what give agents power beyond text generation.
# You are going to write the 4th one yourself — flag_merchant.
#
# WHY THIS MATTERS:
#   In production, agents need write-path tools (flag, alert, insert, publish).
#   This task teaches you the full tool contract:
#     write the function → register it → describe it → verify the agent uses it.
#
# SUCCESS CRITERION:
#   agent_outputs/flagged_merchants.json must exist with at least 1 entry.
#   react_trace.json must show  Action: flag_merchant  at least once.
# ─────────────────────────────────────────────────────────────────────────────

def student_build_task():

    print("\n" + "═"*70)
    print("STUDENT BUILD TASK — Extend the ReAct agent with a new tool")
    print("═"*70)
    print("""
WHAT TO BUILD:
  A tool called flag_merchant that:
  ▸ Accepts a string like: "MRC001, high volume with low average amount"
    (merchant_id is everything before the first comma; reason is everything after)
  ▸ Appends this dict to agent_outputs/flagged_merchants.json:
      {"merchant_id": "MRC001", "reason": "...", "flagged_at": "<ISO timestamp>"}
    (load existing list if file exists, append, save back — do NOT overwrite)
  ▸ Returns the string: "Merchant MRC001 flagged: high volume with low average amount"

3 THINGS YOU MUST CHANGE IN THIS FILE:
  Step 1 — implement tool_flag_merchant below (replace the pass)
  Step 2 — add it to TOOLS:           TOOLS["flag_merchant"] = tool_flag_merchant
  Step 3 — add its description to TOOL_DESCRIPTIONS (find the string ~line 128)
            e.g.: flag_merchant(merchant_id, reason) — Flag a merchant as suspicious

  ⚠ Without Step 3 the agent will NEVER call your tool.
    The LLM can only use tools it is told about in the system prompt.
    This is the most common mistake — fix Step 3 first if the agent ignores your tool.
""")

    # ── STEP 1: Implement the function ────────────────────────────────────────
    # Rules: no external libraries beyond os, json, datetime (already imported).
    # ~10 lines of code. Follow the same pattern as tool_query_db above.
    def tool_flag_merchant(input_str: str) -> str:
        """
        Parse input_str into merchant_id and reason (split on first comma).
        Append to OUTPUT_DIR/flagged_merchants.json — load → append → save.
        Return a confirmation string.
        """
        pass  # ← YOUR CODE HERE

    # ── STEP 2: Register in TOOLS ─────────────────────────────────────────────
    # TODO: uncomment and complete this line:
    # TOOLS["flag_merchant"] = tool_flag_merchant

    # ── STEP 3: Update TOOL_DESCRIPTIONS ──────────────────────────────────────
    # Find TOOL_DESCRIPTIONS in this file (around line 128) and add:
    #   flag_merchant(merchant_id, reason) — Flag a merchant as suspicious in flagged_merchants.json
    # Save the file. That string goes directly into the LLM system prompt.

    # ── STEP 4: Run the agent with the flagging question ──────────────────────
    # Only uncomment this block after Steps 1–3 are done.
    # ─────────────────────────────────────────────────────────────────────────
    # flag_question = (
    #     "Find ALL merchants where transaction_count > 500 AND avg_amount < 15. "
    #     "For each one, call flag_merchant with their merchant_id and a one-line reason."
    # )
    # flag_result = run_react_agent(flag_question)
    #
    # ── STEP 5: Verify ────────────────────────────────────────────────────────
    # flagged_path = os.path.join(OUTPUT_DIR, "flagged_merchants.json")
    # if os.path.exists(flagged_path):
    #     with open(flagged_path, encoding="utf-8") as f:
    #         flagged = json.load(f)
    #     print(f"\n✅ SUCCESS: {len(flagged)} merchant(s) in flagged_merchants.json")
    #     print("   ──────────────────────────────────────────────────")
    #     print("   KEY EXERCISE: open react_trace.json")
    #     print("   Find the Thought that immediately preceded Action: flag_merchant")
    #     print("   That Thought is the agent deciding your tool is relevant.")
    #     print("   Read it — does the agent's reasoning match what you expected?")
    #     try:
    #         trigger = input("\n   In one sentence: what reasoning triggered flag_merchant? ").strip()
    #     except EOFError:
    #         trigger = ""
    #     flag_result["trigger_reasoning"] = trigger or "NOT ANSWERED"
    #     trace_path = os.path.join(OUTPUT_DIR, "react_trace.json")
    #     with open(trace_path, "w", encoding="utf-8") as f:
    #         json.dump(flag_result, f, indent=2, ensure_ascii=False)
    # else:
    #     print("\n❌ flagged_merchants.json not found.")
    #     print("   Most likely: 'flag_merchant' is missing from TOOL_DESCRIPTIONS.")
    #     print("   Fix Step 3 and re-run. The agent can only call tools it knows exist.")
    # ─────────────────────────────────────────────────────────────────────────

    print("\nComplete Steps 1–5. Show the trainer your flagged_merchants.json before Lab 2.")
    print("The key insight: tools = functions + 2 registration lines. Same in LangChain.")


if __name__ == "__main__":
    main()
    student_build_task()
