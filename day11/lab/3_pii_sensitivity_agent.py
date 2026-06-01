"""
==============================================================================
DAY 11 — LAB 3: PII DETECTION + DATA SENSITIVITY CLASSIFICATION AGENT
==============================================================================

MISSION BRIEFING
----------------
Sigma DataTech just discovered that 3 datasets loaded last quarter contained
customer PAN numbers, phone numbers, and Aadhaar IDs — loaded raw into
Snowflake without masking.

SEBI compliance audit is in 6 weeks. The CTO has mandated: every new CSV
must be scanned for PII BEFORE it touches any database — dev, staging, or prod.

Your agent must:
  → Detect PII columns using regex + LLM reasoning (not just column names)
  → Classify the dataset's sensitivity tier (Public / Internal / Confidential / Restricted)
  → Generate a masking/handling recommendation per PII column
  → Produce a compliance-ready sensitivity report

WHAT YOU WILL LEARN
-------------------
- Pattern-based PII detection (regex for PAN, Aadhaar, phone, email, account numbers)
- LLM-assisted detection for ambiguous columns (emp_nm, cust_ph, acct_no)
- Data sensitivity tiers and how enterprises classify data (SEBI / RBI context)
- Masking strategies: redaction, tokenisation, hashing, format-preserving encryption
- Why column NAME detection alone fails in production (abbreviated column names)

MANUAL FIRST (3 minutes — close your laptop)
----------------------------------------------
Look at this column list:
  full_name, email_address, phone_number, pan_number, account_number,
  city, kyc_status, customer_id

Classify each as: PII / Not PII
Then look at this second list (abbreviated names from a partner file):
  cust_nm, mob_no, acct_no, emp_id, loc_cd, dob_dt, pncd

Can you tell which are PII from the name alone? This is why we need LLM detection.

WHERE THIS FITS
---------------
This agent runs AFTER Lab 2's quality check. Clean rows → PII scan → mask → load.
Capstone Option B teams will wire this into their governance agent.

==============================================================================
OUTPUT
------
  agent_outputs/pii_scan_report.json     — full PII detection results
  agent_outputs/sensitivity_report.json  — data classification + masking plan
==============================================================================
"""

import os, sys, json, re, csv
from datetime import datetime

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import boto3
    import pandas as pd
except ImportError as e:
    print(f"[ERROR] {e}. Run: pip install boto3 pandas")
    sys.exit(1)

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "agent_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_ID = "amazon.nova-pro-v1:0"
REGION   = "us-east-1"

# Use customers_raw.csv (has real PII fields)
INPUT_FILE = os.path.join(DATA_DIR, "customers_raw.csv")
if not os.path.exists(INPUT_FILE):
    print("[ERROR] customers_raw.csv not found. Run sample_data.py first.")
    sys.exit(1)

# ── Bedrock helper ────────────────────────────────────────────────────────────
def call_bedrock(prompt: str, system: str = "", max_tokens: int = 1200) -> str:
    client = boto3.client("bedrock-runtime", region_name=REGION)
    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }
    if system:
        body["system"] = [{"text": system}]
    resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: REGEX-BASED PII DETECTION
# Fast, deterministic, no LLM needed for known patterns.
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 1: REGEX PATTERN-BASED PII DETECTION")
print("="*60)

# PII patterns (India-specific + universal)
PII_PATTERNS = {
    "pan_number":     (r"^[A-Z]{5}[0-9]{4}[A-Z]$",         "Financial ID",   "Restricted"),
    "aadhaar_number": (r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$", "Government ID",  "Restricted"),
    "phone_number":   (r"^(\+91)?[7-9][0-9]{9}$",           "Contact",        "Confidential"),
    "email_address":  (r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$",
                                                              "Contact",        "Confidential"),
    "account_number": (r"^[0-9]{9,18}$",                     "Financial ID",   "Restricted"),
    "credit_card":    (r"^[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}[\s\-]?[0-9]{4}$",
                                                              "Financial ID",   "Restricted"),
    "full_name":      (r"^[A-Z][a-z]+ [A-Z][a-z]+$",        "Identity",       "Confidential"),
    "ip_address":     (r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", "Technical",  "Internal"),
}

df = pd.read_csv(INPUT_FILE)
print(f"\n  File: {os.path.basename(INPUT_FILE)} ({df.shape[0]} rows, {df.shape[1]} cols)")

regex_findings = {}
for col in df.columns:
    sample = df[col].dropna().astype(str).head(50).tolist()
    for pii_type, (pattern, category, sensitivity) in PII_PATTERNS.items():
        matches = sum(1 for v in sample if re.match(pattern, v.strip()))
        match_rate = matches / len(sample) if sample else 0
        if match_rate > 0.5:   # >50% match → high confidence
            regex_findings[col] = {
                "pii_type":    pii_type,
                "category":    category,
                "sensitivity": sensitivity,
                "confidence":  "high",
                "match_rate":  round(match_rate, 2),
                "detection_method": "regex",
            }
            print(f"  ✓ [HIGH CONFIDENCE] '{col}' → {pii_type} ({sensitivity})")
            break
        elif match_rate > 0.2:  # 20-50% → medium confidence
            regex_findings[col] = {
                "pii_type":    pii_type,
                "category":    category,
                "sensitivity": sensitivity,
                "confidence":  "medium",
                "match_rate":  round(match_rate, 2),
                "detection_method": "regex",
            }
            print(f"  ~ [MEDIUM    ] '{col}' → {pii_type} ({sensitivity}) — needs LLM review")
            break

non_pii_cols = [c for c in df.columns if c not in regex_findings]
print(f"\n  Regex scan complete: {len(regex_findings)} PII columns found")
print(f"  Columns needing LLM review: {non_pii_cols}")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: LLM-ASSISTED DETECTION (ambiguous columns)
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 2: LLM-ASSISTED PII DETECTION (AMBIGUOUS COLUMNS)")
print("="*60)

if non_pii_cols:
    # Build sample data for each non-PII column
    col_samples = {}
    for col in non_pii_cols:
        col_samples[col] = df[col].dropna().astype(str).head(10).tolist()

    llm_prompt = f"""You are a data privacy officer at Sigma DataTech (Indian fintech, SEBI/RBI regulated).

Analyse these dataset columns and their sample values for PII risk.

Columns to analyse:
{json.dumps(col_samples, indent=2)}

Known PII already detected (DO NOT re-assess these): {list(regex_findings.keys())}

For each column, respond with:
- is_pii: true/false
- pii_type: what type of PII (or null if not PII)
- sensitivity_tier: Public / Internal / Confidential / Restricted
- reasoning: one sentence
- masking_recommendation: how to handle (null if not PII)

Return JSON only:
{{
  "column_assessments": [
    {{
      "column": "column_name",
      "is_pii": true/false,
      "pii_type": "...",
      "sensitivity_tier": "...",
      "reasoning": "...",
      "masking_recommendation": "..."
    }}
  ]
}}"""

    print(f"\n  Sending {len(non_pii_cols)} columns to LLM for PII assessment...")
    llm_response = call_bedrock(llm_prompt, max_tokens=1200)

    try:
        start = llm_response.index("{")
        end   = llm_response.rindex("}") + 1
        llm_result = json.loads(llm_response[start:end])
        for assessment in llm_result.get("column_assessments", []):
            col = assessment.get("column")
            if col and assessment.get("is_pii"):
                regex_findings[col] = {
                    "pii_type":    assessment.get("pii_type"),
                    "category":    "LLM-detected",
                    "sensitivity": assessment.get("sensitivity_tier"),
                    "confidence":  "llm",
                    "reasoning":   assessment.get("reasoning"),
                    "masking_recommendation": assessment.get("masking_recommendation"),
                    "detection_method": "llm",
                }
                print(f"  ✓ [LLM      ] '{col}' → {assessment.get('pii_type')} "
                      f"({assessment.get('sensitivity_tier')})")
    except Exception as e:
        print(f"  [WARN] LLM parse error: {e}. Using regex findings only.")

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: SENSITIVITY CLASSIFICATION + MASKING PLAN
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "="*60)
print("STEP 3: DATASET SENSITIVITY TIER + MASKING PLAN")
print("="*60)

# Determine highest sensitivity tier
tier_order = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}
max_tier = "Public"
for finding in regex_findings.values():
    s = finding.get("sensitivity", "Public")
    if tier_order.get(s, 0) > tier_order.get(max_tier, 0):
        max_tier = s

# Generate masking recommendations for each PII column
MASKING_STRATEGIES = {
    "pan_number":     "Format-preserving tokenisation (PAN structure preserved, value replaced)",
    "aadhaar_number": "Redaction — store only last 4 digits (UIDAI guideline)",
    "phone_number":   "Partial masking: show last 4 digits only (+91 XXXXXX1234)",
    "email_address":  "Domain-preserve masking: user part → hash@domain.com",
    "account_number": "Tokenisation with vault — store token, retrieve on audit",
    "full_name":      "Pseudonymisation — replace with consistent fake name per customer_id",
    "credit_card":    "PCI-DSS tokenisation — mandatory, no exceptions",
}

masking_plan = []
for col, info in regex_findings.items():
    pii_type = info.get("pii_type", "")
    strategy = (MASKING_STRATEGIES.get(pii_type)
                or info.get("masking_recommendation")
                or "Encryption at rest + column-level access control")
    masking_plan.append({
        "column":     col,
        "pii_type":   pii_type,
        "sensitivity": info.get("sensitivity"),
        "confidence": info.get("confidence"),
        "masking_strategy": strategy,
        "detect_method":    info.get("detection_method"),
    })
    print(f"  {col:20} → {strategy[:60]}")

# ─────────────────────────────────────────────────────────────────────────────
# SAVE REPORTS
# ─────────────────────────────────────────────────────────────────────────────

pii_report = {
    "agent":           "PIISensitivityAgent",
    "run_timestamp":   datetime.now().isoformat(),
    "input_file":      os.path.basename(INPUT_FILE),
    "total_columns":   df.shape[1],
    "pii_columns_found": len(regex_findings),
    "dataset_sensitivity_tier": max_tier,
    "pii_findings":    regex_findings,
}

sensitivity_report = {
    "agent":           "PIISensitivityAgent",
    "run_timestamp":   datetime.now().isoformat(),
    "input_file":      os.path.basename(INPUT_FILE),
    "dataset_classification": max_tier,
    "load_restriction": {
        "Public":       "No restrictions",
        "Internal":     "Internal systems only — no external API exposure",
        "Confidential": "Mask PII before load — column-level access controls required",
        "Restricted":   "BLOCK load until PII masked — compliance sign-off required",
    }.get(max_tier, "Unknown"),
    "masking_plan": masking_plan,
    "compliance_notes": [
        "PAN numbers: RBI circular 2023-09 requires format-preserving tokenisation",
        "Aadhaar: UIDAI mandate — only last 4 digits may be stored",
        "All Restricted data requires DLP tool scan before prod load",
    ]
}

pii_path  = os.path.join(OUTPUT_DIR, "pii_scan_report.json")
sens_path = os.path.join(OUTPUT_DIR, "sensitivity_report.json")

with open(pii_path, "w")  as f: json.dump(pii_report, f, indent=2)
with open(sens_path, "w") as f: json.dump(sensitivity_report, f, indent=2)

# ─────────────────────────────────────────────────────────────────────────────
# JUDGMENT QUESTION
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JUDGMENT QUESTION")
print("="*60)
print(f"""
  The PII agent classified this dataset as: {max_tier}
  Load restriction: {sensitivity_report['load_restriction']}

  A partner sends a CSV with column names: emp_nm, mob_no, acct_no, dob_dt
  The regex scanner finds ZERO PII (abbreviated names).
  The LLM correctly identifies all 4 as PII.

  Should you always run the LLM scan even when regex finds nothing?
  What is the cost vs risk tradeoff?
""")
judgment = input("  Your answer (1-2 sentences): ").strip() or "NOT ANSWERED"

with open(sens_path) as f: data = json.load(f)
data["student_judgment"] = judgment
with open(sens_path, "w") as f: json.dump(data, f, indent=2)

# ── Final summary ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("LAB 3 COMPLETE — PII & SENSITIVITY AGENT")
print("="*60)
print(f"""
  Dataset: {os.path.basename(INPUT_FILE)}
  Sensitivity tier: {max_tier}
  PII columns found: {len(regex_findings)} of {df.shape[1]}

  Detection methods used:
    Regex (high confidence)   : fast, cheap, deterministic
    LLM (ambiguous columns)   : slower, expensive, handles abbreviations

  Production pattern:
    1. Regex scan first (catches 90% of cases instantly)
    2. LLM scan only for columns regex didn't classify
    3. Human review for "Restricted" columns before first load

  Output files:
    pii_scan_report.json    — column-level PII findings
    sensitivity_report.json — masking plan + load restrictions
""")
