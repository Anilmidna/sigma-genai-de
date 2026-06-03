"""
lineage_agent.py — Lineage & Governance Agent
Day 13 · Sigma Intelligence Platform

Two labs, one script:

  LAB 1 — Mystery Domain (Anil assigns mystery_a or mystery_b)
    python lab/lineage_agent.py --lab 1 --mystery lab/mystery_a/
    python lab/lineage_agent.py --lab 1 --mystery lab/mystery_b/

  LAB 2 — Your Own Sigma DataTech dbt Project (client deliverable)
    python lab/lineage_agent.py --lab 2 --models ../day6/sigma_dbt/models/

Lab 1: You don't know the company. Guess the industry. Govern blind.
Lab 2: Your own project. Known domain. Produce the client catalogue.
"""

import argparse, boto3, json, os, re, sys, time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

REGION   = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
MODEL_ID = "amazon.nova-lite-v1:0"

SCRIPT_DIR  = Path(__file__).parent
OUTPUT_DIR  = SCRIPT_DIR / "agent_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Prompts ────────────────────────────────────────────────────────────────────

INDUSTRY_PROMPT = """You are a data governance analyst.
You have been given SQL models from an UNKNOWN company's data warehouse.
You do not know what industry this is. Figure it out from the column names.

Look at ALL these SQL files together and answer:
1. What industry/business is this? (e.g. HR software, food delivery, healthcare, e-commerce)
2. What does this company actually DO? (2 sentences)
3. What are your top 3 clues from the column names?
4. Confidence level: HIGH / MEDIUM / LOW

Return ONLY valid JSON:
{{
  "industry": "one word or short phrase",
  "what_they_do": "2 sentences",
  "top_clues": ["clue 1", "clue 2", "clue 3"],
  "confidence": "HIGH | MEDIUM | LOW"
}}

SQL files:
{all_sql}
"""

MODEL_PROMPT = """You are a senior data governance analyst.
You are cataloguing a table from an UNKNOWN company's data warehouse.

Analyse this SQL model and return ONLY valid JSON:
{{
  "source_tables": ["tables this model reads from"],
  "column_lineage": [
    {{
      "target_column": "column name",
      "source_table": "where it comes from",
      "source_column": "original column name",
      "transformation": "what changed, or 'direct'"
    }}
  ],
  "pii_columns": [
    {{
      "column": "column name",
      "pii_type": "NAME | EMAIL | PHONE | ADDRESS | GOV_ID | FINANCIAL | LOCATION | BIOMETRIC",
      "severity": "LOW | MEDIUM | HIGH | CRITICAL",
      "real_world_risk": "one sentence: what happens if this column leaks"
    }}
  ],
  "business_description": "2-3 sentences in plain English",
  "who_should_access": "which team/role should be allowed to query this table",
  "who_should_NOT_access": "which team/role should be explicitly blocked",
  "sensitivity_level": "PUBLIC | INTERNAL | CONFIDENTIAL | RESTRICTED",
  "governance_flag": "any unusual governance concern about this specific table"
}}

Model name: {model_name}
SQL:
{sql}
"""

THREE_QUESTIONS_PROMPT = """Based on your analysis of this data warehouse, answer these
three governance questions. Be specific — reference actual table and column names.

Return ONLY valid JSON:
{{
  "q1_most_damaging_column": {{
    "column": "table_name.column_name",
    "why": "2-3 sentences — what a malicious actor could do with this single column"
  }},
  "q2_hacker_target_table": {{
    "table": "table_name",
    "why": "2-3 sentences — what a hacker could do with SELECT access to this table",
    "damage_estimate": "scale: minor nuisance | significant harm | catastrophic"
  }},
  "q3_europe_expansion": {{
    "columns_needing_consent": ["table.column1", "table.column2", "table.column3"],
    "why": "2 sentences — why these specifically require GDPR consent",
    "columns_already_compliant": ["table.column (reason)"]
  }}
}}

Here is the full catalogue you generated:
{catalogue_json}
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def call_bedrock(prompt: str) -> str:
    bedrock = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 2000, "temperature": 0.1},
    }
    resp   = bedrock.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    result = json.loads(resp["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def parse_json(raw: str) -> dict:
    try:
        cleaned = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`").strip()
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {"error": "unparseable", "raw": raw[:300]}


def analyse_model(model_path: Path) -> dict:
    sql    = model_path.read_text()
    prompt = MODEL_PROMPT.format(model_name=model_path.stem, sql=sql)
    raw    = call_bedrock(prompt)
    result = parse_json(raw)
    result["model_name"]  = model_path.stem
    result["sql_lines"]   = len(sql.splitlines())
    result["analysed_at"] = datetime.now(timezone.utc).isoformat()
    return result


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Day 13 Lineage & Governance Agent")
    parser.add_argument("--lab",     required=True, choices=["1", "2"],
                        help="1 = Mystery Domain  |  2 = Your Sigma DataTech project")
    parser.add_argument("--mystery", default=None,
                        help="[Lab 1] Path to mystery folder: lab/mystery_a/ or lab/mystery_b/")
    parser.add_argument("--models",  default=None,
                        help="[Lab 2] Path to your dbt models folder: ../day6/sigma_dbt/models/")
    args = parser.parse_args()

    # ── Resolve the models folder based on lab ─────────────────────────────────
    if args.lab == "1":
        if not args.mystery:
            print("[ERROR] --mystery is required for Lab 1")
            print("  Example: python lab/lineage_agent.py --lab 1 --mystery lab/mystery_a/")
            sys.exit(1)
        models_dir  = Path(args.mystery)
        folder_name = models_dir.name          # mystery_a or mystery_b
        output_file = OUTPUT_DIR / f"catalogue_{folder_name}.json"
        is_mystery  = True

    else:  # lab 2
        if not args.models:
            print("[ERROR] --models is required for Lab 2")
            print("  Example: python lab/lineage_agent.py --lab 2 --models ../day6/sigma_dbt/models/")
            sys.exit(1)
        models_dir  = Path(args.models)
        folder_name = "sigma_datatech"
        output_file = OUTPUT_DIR / "catalogue_sigma.json"
        is_mystery  = False

    if not models_dir.exists():
        print(f"[ERROR] Folder not found: {models_dir}")
        sys.exit(1)

    sql_files = sorted(models_dir.glob("*.sql"))
    if not sql_files:
        print(f"[ERROR] No .sql files found in {models_dir}")
        sys.exit(1)

    guess_file = OUTPUT_DIR / "mystery_guess.json"

    # ── Header ─────────────────────────────────────────────────────────────────
    print("=" * 60)
    if is_mystery:
        print("LAB 1 — MYSTERY DOMAIN GOVERNANCE AGENT")
    else:
        print("LAB 2 — SIGMA DATATECH GOVERNANCE AGENT (Client Deliverable)")
    print("=" * 60)
    print(f"  Folder    : {models_dir}")
    print(f"  Tables    : {len(sql_files)}")
    print(f"  Output    : {output_file.name}")
    print(f"  Model     : {MODEL_ID}")
    print("=" * 60)
    print()

    # ── Manual-first gate ──────────────────────────────────────────────────────
    if is_mystery:
        print("You have received an UNKNOWN dbt project.")
        print("Column names are your only clues.")
        print()
        print("─" * 60)
        print("BEFORE THE AGENT RUNS — your manual assessment:")
        print("─" * 60)
        industry_guess = input("\nWhat industry do you think this is? ").strip()
        sensitive_cols = input("Name 3 columns you think are most sensitive: ").strip()
        hacker_target  = input("Which table would a hacker target first? ").strip()

        guess_file.write_text(json.dumps({
            "lab":              "1 - Mystery Domain",
            "folder":           folder_name,
            "industry_guess":   industry_guess,
            "sensitive_columns": sensitive_cols,
            "hacker_target":    hacker_target,
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        print("\nSaved. Now watch the agent analyse the same project.\n")

    else:
        print("This is YOUR Sigma DataTech project — you know this warehouse.")
        print()
        print("─" * 60)
        print("BEFORE THE AGENT RUNS — your manual assessment:")
        print("─" * 60)
        sensitive_cols = input("\nName the 3 most sensitive columns in your warehouse: ").strip()
        hacker_target  = input("Which table would cause the most damage if leaked? ").strip()
        gdpr_risk      = input("If Sigma DataTech expanded to Europe, which table needs GDPR consent first? ").strip()

        guess_file.write_text(json.dumps({
            "lab":              "2 - Sigma DataTech",
            "sensitive_columns": sensitive_cols,
            "hacker_target":    hacker_target,
            "gdpr_risk":        gdpr_risk,
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }, indent=2))
        print("\nSaved. Now the agent catalogues your entire warehouse.\n")

    print("─" * 60)

    # ── Phase 1: Industry identification (mystery only) ───────────────────────
    all_sql = "\n\n---\n\n".join(
        f"-- {f.stem}\n{f.read_text()}" for f in sql_files
    )

    if is_mystery:
        print("\n[PHASE 1] Agent reads all SQL files and guesses the industry...")
        industry_raw    = call_bedrock(INDUSTRY_PROMPT.format(all_sql=all_sql))
        industry_result = parse_json(industry_raw)
        print(f"  Agent says   : {industry_result.get('industry', '?')} "
              f"(confidence: {industry_result.get('confidence', '?')})")
        print(f"  What they do : {industry_result.get('what_they_do', '?')}")
        print(f"  Top clues    : {industry_result.get('top_clues', [])}")
    else:
        industry_result = {
            "industry":    "Sigma DataTech — Fintech payments platform",
            "what_they_do": "Processes merchant transactions in India. "
                            "Tracks GMV, SLA breaches, and customer payments.",
            "top_clues":   ["merchant_name", "transaction_id", "gmv_inr"],
            "confidence":  "HIGH",
        }
        print("\n[PHASE 1] Industry: Sigma DataTech (known — no guess needed)")
    print()

    # ── Step 3: Analyse each model ────────────────────────────────────────────
    print("[PHASE 2] Cataloguing each table...\n")

    catalogue = {
        "mystery_folder":   folder_name,
        "industry_analysis": industry_result,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "tables":           {},
    }

    pii_surface = []
    total_start = time.time()

    for i, sql_file in enumerate(sql_files, 1):
        print(f"  [{i}/{len(sql_files)}] {sql_file.stem}...", end=" ", flush=True)
        t0 = time.time()

        result = analyse_model(sql_file)
        catalogue["tables"][sql_file.stem] = result
        elapsed = round(time.time() - t0, 1)

        pii_count = len(result.get("pii_columns", []))
        print(f"done ({elapsed}s) | PII: {pii_count} | "
              f"{result.get('sensitivity_level','?')}")

        for p in result.get("pii_columns", []):
            pii_surface.append({
                "table":      sql_file.stem,
                "column":     p.get("column","?"),
                "pii_type":   p.get("pii_type","?"),
                "severity":   p.get("severity","?"),
                "risk":       p.get("real_world_risk",""),
            })

    # ── Step 4: Answer the three governance questions ─────────────────────────
    print("\n[PHASE 3] Answering the three governance questions...")
    cat_summary = json.dumps({k: v for k, v in catalogue["tables"].items()}, indent=2)
    q_raw    = call_bedrock(THREE_QUESTIONS_PROMPT.format(catalogue_json=cat_summary[:8000]))
    q_result = parse_json(q_raw)

    catalogue["three_questions"] = q_result
    catalogue["pii_surface_area"] = pii_surface
    catalogue["summary"] = {
        "total_tables":      len(sql_files),
        "total_pii_columns": len(pii_surface),
        "critical_columns":  sum(1 for p in pii_surface if p["severity"] == "CRITICAL"),
        "high_columns":      sum(1 for p in pii_surface if p["severity"] == "HIGH"),
        "analysis_seconds":  round(time.time() - total_start, 1),
    }

    output_file.write_text(json.dumps(catalogue, indent=2))

    # ── Results ───────────────────────────────────────────────────────────────
    elapsed_total = round(time.time() - total_start, 1)
    print()
    print("=" * 60)
    print("GOVERNANCE CATALOGUE COMPLETE")
    print("=" * 60)
    print(f"  Output         : {output_file}")
    print(f"  Tables         : {len(sql_files)}")
    print(f"  PII columns    : {len(pii_surface)}")
    print(f"  CRITICAL       : {catalogue['summary']['critical_columns']}")
    print(f"  Time           : {elapsed_total}s")
    print()
    print("  PII surface area (sorted by severity):")
    for p in sorted(pii_surface,
                    key=lambda x: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}.get(x["severity"],4)):
        print(f"    [{p['severity']:8}] {p['table']}.{p['column']}  ({p['pii_type']})")
    print()

    # ── Compare student guess vs agent ────────────────────────────────────────
    agent_critical = [f"{p['table']}.{p['column']}"
                      for p in pii_surface if p["severity"] in ("CRITICAL","HIGH")][:3]
    q1 = q_result.get("q1_most_damaging_column", {})
    q2 = q_result.get("q2_hacker_target_table", {})
    q3 = q_result.get("q3_europe_expansion", {})

    print("─" * 60)
    print("YOUR ANSWERS vs THE AGENT")
    print("─" * 60)

    if is_mystery:
        print(f"  Your industry guess    : {industry_guess}")
        print(f"  Agent industry guess   : {industry_result.get('industry','?')} "
              f"({industry_result.get('confidence','?')} confidence)")
        print()

    print(f"  Your sensitive columns : {sensitive_cols}")
    print(f"  Agent's top findings   : {', '.join(agent_critical)}")
    print()
    print(f"  Your hacker target     : {hacker_target}")
    print(f"  Agent hacker target    : {q2.get('table','?')} "
          f"({q2.get('damage_estimate','?')})")
    print()
    print("  Agent's three governance answers:")
    print(f"  Q1 Most damaging column : {q1.get('column','?')}")
    print(f"     {q1.get('why','?')[:120]}...")
    print(f"  Q2 Hacker table         : {q2.get('table','?')}")
    print(f"     {q2.get('why','?')[:120]}...")
    print(f"  Q3 GDPR columns         : {q3.get('columns_needing_consent',[])}")
    print()
    if is_mystery:
        print("  Where did domain knowledge give YOU an edge over the AI?")
    else:
        print("  You know this warehouse better than the agent does.")
        print("  Find ONE thing the agent got wrong and explain why.")
    print("=" * 60)


if __name__ == "__main__":
    main()
