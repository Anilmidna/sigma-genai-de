"""
Day 8 — Sprint 2: Documentation Generator
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION BRIEFING:
  Sigma DataTech's buggy_pipeline.py has zero documentation.
  A new joiner joined the team yesterday. They can't understand
  what the pipeline does, why it was written this way, or what
  to do when it fails. The post-incident review meeting is in
  2 hours. The tech lead just dropped it in your lap:
  "Get this thing documented before the review. All of it."

  A senior DE would take a full day for this.
  AI does it in 5 minutes.
  Your job: verify what AI produces is actually correct.

MANUAL FIRST (do this BEFORE running the script):
  Open buggy_pipeline.py RIGHT NOW. Read it for 2 minutes.
  Write down answers to these three questions:
    1. What are the 3 main data transformations this pipeline does?
    2. What is the biggest bug or risk you can see just by reading it?
    3. What would a runbook need to say about the failure mode in
       transform_bronze_to_silver?
  THEN run this script and compare AI's answers to yours.

WHERE THIS FITS IN THE PLATFORM:
  Day 8 Sprint 1 (done): You reviewed the pipeline code
  Day 8 Sprint 2 (now):  AI documents the pipeline in 5 minutes
  Day 8 Sprint 3 (next): AI generates tests — including at least
                          one bad test you must find
  Day 12: A self-heal agent reads this runbook to decide how to
           recover from pipeline failures automatically

HOW TO RUN:
  cd repo/day8/lab
  python 2_doc_generator.py

OUTPUT:
  devops_brain/documented_pipeline.py   <- annotated source
  devops_brain/runbook.md               <- Confluence-ready runbook
  devops_brain/design_doc.md            <- 1-page technical design
  devops_brain/doc_report.json          <- summary + your judgment

IMPORTANT: SPEND 5 MINUTES READING THIS FILE. YOU HAVE A QUIZ ON IT.
═══════════════════════════════════════════════════════════════
"""

import sys
import os
import json
import boto3
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Configuration ──────────────────────────────────────────────────────────
MODEL_ID_PRO  = "amazon.nova-pro-v1:0"
MODEL_ID_LITE = "amazon.nova-lite-v1:0"
REGION        = "us-east-1"

OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "devops_brain")
SOURCE_FILE  = os.path.join(os.path.dirname(__file__), "buggy_pipeline.py")

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
        system_text: System prompt text setting the AI's role.
        user_text:   The user-turn prompt.
        max_tokens:  Maximum tokens for the response.

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
        text:       Raw AI response text.
        fence_lang: Optional language tag (e.g. "python", "markdown").

    Returns:
        Cleaned text with fences stripped.
    """
    text = text.strip()
    tag = f"```{fence_lang}" if fence_lang else "```"
    if text.startswith(tag):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def read_source() -> str:
    """Read buggy_pipeline.py from disk."""
    if not os.path.exists(SOURCE_FILE):
        print(f"[ERROR] Source file not found: {SOURCE_FILE}")
        print("        Expected: buggy_pipeline.py in the same lab/ folder.")
        sys.exit(1)
    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 — Annotate the pipeline source (Nova Pro)
# ══════════════════════════════════════════════════════════════════════════

def generate_documented_source(source_code: str) -> tuple[str, dict]:
    """
    Add full docstrings, type hints, and inline comments to every function.

    Uses Nova Pro because this requires precise reasoning about what each
    function does, not just pattern-matching.

    Args:
        source_code: Raw source of buggy_pipeline.py.

    Returns:
        Tuple of (annotated_python_code, usage_dict).
    """
    system = (
        "You are a senior Python engineer at a fintech company. "
        "You write clear, precise documentation for production data pipelines. "
        "You do not change logic — you only ADD docstrings, type hints, and inline comments. "
        "You flag bugs with a comment starting with: # BUG:"
    )

    user = f"""The following Python file has zero documentation.
Add FULL documentation to every function:
- A Google-style docstring (Args, Returns, Raises sections where applicable)
- Type hints on every function signature
- Inline comments explaining non-obvious logic
- A # BUG: comment on every line that contains a real bug or security risk
  (hardcoded credentials, missing null checks, SQL injection, bare except, etc.)

Do NOT change any logic. Only add documentation.
Return ONLY the complete annotated Python file. No markdown fences. No explanation.

SOURCE FILE (buggy_pipeline.py):
{source_code}"""

    print("\n[Bedrock] Step 1: Annotating source with docstrings + type hints...")
    print(f"          Model: {MODEL_ID_PRO} | Source: {len(source_code):,} chars")

    annotated, usage = call_bedrock(MODEL_ID_PRO, system, user, max_tokens=6000)
    annotated = strip_fences(annotated, "python")

    print(f"          Done. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")
    return annotated, usage


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 — Generate Confluence-ready runbook (Nova Pro)
# ══════════════════════════════════════════════════════════════════════════

def generate_runbook(source_code: str) -> tuple[str, dict]:
    """
    Generate a Confluence-ready runbook in Markdown format.

    Covers pipeline overview, steps, failure modes, recovery actions,
    and escalation contacts using fictional Sigma DataTech names.

    Args:
        source_code: Raw source of buggy_pipeline.py.

    Returns:
        Tuple of (runbook_markdown, usage_dict).
    """
    system = (
        "You are a senior data engineering tech lead at Sigma DataTech. "
        "You write concise, actionable runbooks that on-call engineers can follow at 3 AM. "
        "Use Markdown suitable for Confluence. Be specific — no vague instructions."
    )

    user = f"""Write a Confluence-ready runbook for the following pipeline.

Use fictional but realistic names for Sigma DataTech team members:
  - On-call DE:        Priya Nair (priya.nair@sigmadatatech.in, +91-98400-11111)
  - Tech Lead:         Arjun Mehta (arjun.mehta@sigmadatatech.in)
  - Platform Manager:  Kavya Reddy (kavya.reddy@sigmadatatech.in)

RUNBOOK MUST INCLUDE:
1. **Pipeline Overview** — what this pipeline does, why it runs, what breaks if it stops
2. **Pipeline Steps** — numbered, one sentence each, referencing actual function names
3. **Schedule / Trigger** — when does this run? what kicks it off?
4. **Failure Modes** — at least 5 specific failure scenarios with root cause + symptom
5. **Recovery Actions** — step-by-step instructions for each failure mode above
6. **Known Bugs** — list the actual bugs visible in the code (credentials, null handling, etc.)
7. **Escalation Contacts** — who to call, in what order, at what severity threshold
8. **Data Quality Checks** — what to verify after a successful run

PIPELINE SOURCE:
{source_code}

Return ONLY the Markdown content. No preamble. No code fences."""

    print("\n[Bedrock] Step 2: Generating Confluence runbook...")
    print(f"          Model: {MODEL_ID_PRO}")

    runbook, usage = call_bedrock(MODEL_ID_PRO, system, user, max_tokens=4000)
    runbook = strip_fences(runbook, "markdown")

    print(f"          Done. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")
    return runbook, usage


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 — Generate 1-page technical design doc (Nova Lite)
# ══════════════════════════════════════════════════════════════════════════

def generate_design_doc(source_code: str) -> tuple[str, dict]:
    """
    Generate a 1-page technical design summary using Nova Lite.

    Includes data flow diagram (ASCII), key design decisions, and
    known limitations. Nova Lite is sufficient for structured summaries.

    Args:
        source_code: Raw source of buggy_pipeline.py.

    Returns:
        Tuple of (design_doc_markdown, usage_dict).
    """
    system = (
        "You are a data architect. You write concise technical design documents "
        "for data pipelines. You use ASCII diagrams, not image links."
    )

    user = f"""Write a 1-page technical design document for this pipeline.

REQUIRED SECTIONS:
1. **What This Pipeline Does** — 2-3 sentences max
2. **Data Flow Diagram** — ASCII art showing: Source → Bronze → Silver → Gold
   Include table names, key transformations at each arrow
3. **Key Design Decisions** — 3-4 bullet points explaining WHY it was designed this way
4. **Known Limitations** — 3-4 bullet points of real limitations (based on the code, not generic)
5. **Dependencies** — what external systems, tables, or files this pipeline needs to run

Keep it to one page (under 400 words). Use Markdown.

PIPELINE SOURCE:
{source_code}

Return ONLY the Markdown. No preamble. No code fences."""

    print("\n[Bedrock] Step 3: Generating technical design doc...")
    print(f"          Model: {MODEL_ID_LITE} (design summaries don't need Pro reasoning)")

    design_doc, usage = call_bedrock(MODEL_ID_LITE, system, user, max_tokens=2000)
    design_doc = strip_fences(design_doc, "markdown")

    print(f"          Done. Tokens: {usage['inputTokens']} in / {usage['outputTokens']} out")
    return design_doc, usage


# ══════════════════════════════════════════════════════════════════════════
# ACCOUNTABILITY GATE
# ══════════════════════════════════════════════════════════════════════════

def accountability_gate(runbook: str) -> str:
    """
    Show the AI-generated runbook and ask the student one critical question.

    This gate forces the student to read and evaluate the AI output before
    it is accepted as "done". Empty answers are saved as NOT ANSWERED.

    Args:
        runbook: The AI-generated runbook markdown text.

    Returns:
        The student's answer as a string.
    """
    print("\n" + "=" * 65)
    print("  AI-GENERATED RUNBOOK (first 60 lines shown)")
    print("=" * 65)
    lines = runbook.split("\n")
    for line in lines[:60]:
        print(" ", line)
    if len(lines) > 60:
        print(f"  ... ({len(lines) - 60} more lines — see devops_brain/runbook.md)")
    print("=" * 65)

    print()
    print("  AI wrote the runbook above.")
    print("  → Name ONE thing it got wrong or missed that you would add")
    print("    as a real DE. (1 sentence):")
    print()

    try:
        answer = input("  Your answer: ").strip()
    except (EOFError, KeyboardInterrupt):
        answer = ""

    if not answer:
        answer = "NOT ANSWERED"

    return answer


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("\n" + "=" * 65)
    print("  SPRINT 2: Documentation Generator")
    print("  Sigma Intelligence Platform | Day 8")
    print("=" * 65)

    # ── MANUAL FIRST REMINDER ──────────────────────────────────
    print()
    print("  MANUAL FIRST — Before we run anything:")
    print("  Open buggy_pipeline.py and spend 2 minutes reading it.")
    print("  Answer these in your head (or on paper):")
    print("    1. What are the 3 main data transformations this pipeline does?")
    print("    2. What is the biggest bug or risk you can see just by reading?")
    print("    3. What failure mode would a runbook need to cover?")
    print()
    input("  [Press Enter when you have answers, then AI goes to work] ")

    # ── Load source ─────────────────────────────────────────────
    print(f"\n[INFO] Reading buggy_pipeline.py ({SOURCE_FILE})")
    source_code = read_source()
    print(f"       Source: {len(source_code):,} chars, {len(source_code.splitlines())} lines")

    total_usage = {"inputTokens": 0, "outputTokens": 0}

    # ── Step 1: Annotated source ─────────────────────────────────
    annotated_code, usage1 = generate_documented_source(source_code)
    total_usage["inputTokens"]  += usage1["inputTokens"]
    total_usage["outputTokens"] += usage1["outputTokens"]

    doc_path = os.path.join(OUTPUT_DIR, "documented_pipeline.py")
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(annotated_code)
    print(f"\n[OK] Saved: devops_brain/documented_pipeline.py")
    print(f"     Lines: {len(annotated_code.splitlines())} "
          f"(original: {len(source_code.splitlines())})")

    # ── Step 2: Runbook ──────────────────────────────────────────
    runbook, usage2 = generate_runbook(source_code)
    total_usage["inputTokens"]  += usage2["inputTokens"]
    total_usage["outputTokens"] += usage2["outputTokens"]

    runbook_path = os.path.join(OUTPUT_DIR, "runbook.md")
    with open(runbook_path, "w", encoding="utf-8") as f:
        f.write(runbook)
    print(f"\n[OK] Saved: devops_brain/runbook.md")
    print(f"     Lines: {len(runbook.splitlines())}")

    # ── Step 3: Design doc ───────────────────────────────────────
    design_doc, usage3 = generate_design_doc(source_code)
    total_usage["inputTokens"]  += usage3["inputTokens"]
    total_usage["outputTokens"] += usage3["outputTokens"]

    design_path = os.path.join(OUTPUT_DIR, "design_doc.md")
    with open(design_path, "w", encoding="utf-8") as f:
        f.write(design_doc)
    print(f"\n[OK] Saved: devops_brain/design_doc.md")
    print(f"     Lines: {len(design_doc.splitlines())}")

    # ── Accountability gate ──────────────────────────────────────
    student_judgment = accountability_gate(runbook)

    # ── Save summary report ──────────────────────────────────────
    report = {
        "sprint": "doc_generator",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_file": "buggy_pipeline.py",
        "source_chars": len(source_code),
        "source_lines": len(source_code.splitlines()),
        "models_used": {
            "annotated_source": MODEL_ID_PRO,
            "runbook": MODEL_ID_PRO,
            "design_doc": MODEL_ID_LITE,
        },
        "token_usage": {
            "step1_annotate": {"input": usage1["inputTokens"], "output": usage1["outputTokens"]},
            "step2_runbook":  {"input": usage2["inputTokens"], "output": usage2["outputTokens"]},
            "step3_design":   {"input": usage3["inputTokens"], "output": usage3["outputTokens"]},
            "total_input":    total_usage["inputTokens"],
            "total_output":   total_usage["outputTokens"],
        },
        "output_files": {
            "documented_pipeline": "devops_brain/documented_pipeline.py",
            "runbook": "devops_brain/runbook.md",
            "design_doc": "devops_brain/design_doc.md",
        },
        "student_judgment": student_judgment,
    }

    report_path = os.path.join(OUTPUT_DIR, "doc_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n[OK] Saved: devops_brain/doc_report.json")

    # ── Debrief ──────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  DEBRIEF — What Just Happened")
    print("=" * 65)
    print()
    print("  WHAT JUST HAPPENED:")
    print("    AI read 313 lines of undocumented Python and produced:")
    print("      1. A fully annotated source file with docstrings + type hints")
    print("         — including # BUG: markers on every real defect")
    print("      2. A Confluence-ready runbook with failure modes and recovery steps")
    print("      3. A 1-page design doc with ASCII data flow diagram")
    print("    All three outputs took under 30 seconds of wall time.")
    print("    A human DE would spend 3-4 hours on the same work.")
    print()
    print("  WHAT AI GOT RIGHT:")
    print("    1. Identified the hardcoded credentials as a security risk")
    print("       — this is prominent in its training data (OWASP Top 10)")
    print("    2. Documented every function's purpose correctly")
    print("       — even single-letter variable names were decoded from context")
    print("    3. Generated realistic escalation contacts and recovery steps")
    print("       — runbook structure is a well-known pattern AI handles well")
    print()
    print("  WHAT AI GETS WRONG (always verify these):")
    print("    1. The 'Known Bugs' section may MISS bugs that require runtime context")
    print("       Example: enrich_with_merchant() opens a new DB connection every call")
    print("       — AI may document the SQL injection but miss the connection leak")
    print("    2. Recovery steps are often generic ('check the logs', 'restart the job')")
    print("       — real runbooks need exact commands, paths, and log locations")
    print("    3. AI cannot know your actual on-call rotation, SLA windows, or")
    print("       paging thresholds — those must be filled in by a human")
    print()
    print("  THE RULE TO REMEMBER:")
    print("    AI drafts the runbook in 5 minutes. You spend 20 minutes making it")
    print("    accurate. That is still 5x faster than writing from scratch — but")
    print("    only if you actually review it.")
    print()
    print("  WHERE THIS FITS NEXT:")
    print("    Sprint 3 (next): AI generates a pytest suite AND Great Expectations")
    print("    checks for this exact pipeline. One test will be intentionally wrong.")
    print("    Your job is to find it.")
    print(f"{'=' * 65}")
    print()
    print("  Next: python 3_testing_sprint.py")
    print()


if __name__ == "__main__":
    main()
