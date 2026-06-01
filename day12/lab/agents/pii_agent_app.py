"""
PII Detection Agent — FastAPI app on port 8003
POST /scan-pii  → two-layer PII scan (regex + LLM), masks or blocks, saves to RAG memory
GET  /health    → health check
"""

import json, os, re, sys
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import call_bedrock, get_logger, read_s3_json_gz, parse_json_response
from agent_memory import AgentMemory

app    = FastAPI(title="PII Detection Agent", version="1.0")
logger = get_logger("pii-agent")
memory = AgentMemory()

REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
OUTPUT_DIR = os.getenv("PLATFORM_DIR", os.path.join(os.path.dirname(__file__), "..")) + "/agent_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PII_PATTERNS = {
    "pan_number":     (r"^[A-Z]{5}[0-9]{4}[A-Z]$",                           "Financial ID",  "Restricted"),
    "aadhaar_number": (r"^[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}$",                  "Govt ID",       "Restricted"),
    "phone_number":   (r"^(\+91)?[7-9][0-9]{9}$",                             "Contact",       "Confidential"),
    "account_number": (r"^[0-9]{9,18}$",                                      "Financial ID",  "Restricted"),
    "pin_code":       (r"^[1-9][0-9]{5}$",                                    "Location",      "Confidential"),
    "email_address":  (r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$","Contact",      "Confidential"),
}

SENSITIVITY_ORDER = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}

class PIIRequest(BaseModel):
    bucket:   str
    file_key: str
    region:   str = REGION

class PIIResponse(BaseModel):
    status:                   str
    pii_columns_found:        int
    restricted_columns_found: bool
    dataset_sensitivity:      str
    findings:                 dict
    memory_context:           str
    timestamp:                str

def mask_value(value, pii_type):
    v = str(value)
    if pii_type == "phone_number":   return "+91XXXXXX" + v[-4:] if len(v) >= 4 else "XXXX"
    if pii_type == "account_number": return "XXXXXXXX" + v[-4:] if len(v) >= 4 else "XXXX"
    if pii_type == "pin_code":       return v[:2] + "XXXX" if len(v) >= 2 else "XXXX"
    if pii_type == "email_address":  parts = v.split("@"); return "****@" + parts[1] if len(parts)==2 else "****"
    return "XXXX" + v[-4:] if len(v) >= 4 else "XXXX"

@app.post("/scan-pii", response_model=PIIResponse)
async def scan_pii_endpoint(req: PIIRequest):
    import pandas as pd
    logger.info(f"Scanning: {req.file_key}")

    rows = read_s3_json_gz(req.bucket, req.file_key, req.region)
    df   = pd.DataFrame(rows)

    # Layer 1: Regex
    regex_findings = {}
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(50).tolist()
        for pii_type, (pattern, category, sensitivity) in PII_PATTERNS.items():
            matches    = sum(1 for v in sample if re.match(pattern, v.strip()))
            match_rate = matches / len(sample) if sample else 0
            if match_rate > 0.5:
                regex_findings[col] = {"pii_type": pii_type, "sensitivity": sensitivity,
                                       "confidence": "high", "method": "regex"}
                break

    # Layer 2: LLM for unclassified columns
    unclassified = [c for c in df.columns if c not in regex_findings]

    # RAG: retrieve past PII findings for context
    past_findings = memory.retrieve("pii_findings",
                                    f"PII columns: {unclassified}", n_results=2)
    memory_context = "\n".join(past_findings) if past_findings else "No past PII findings retrieved"
    logger.info(f"Regex found {len(regex_findings)} PII cols. RAG retrieved {len(past_findings)} past finding(s)")

    llm_findings = {}
    if unclassified:
        samples = {col: df[col].dropna().astype(str).head(10).tolist() for col in unclassified}
        prompt  = f"""You are a data privacy officer at Sigma DataTech (Indian fintech).

Analyse these columns for PII. Focus on abbreviated names like cust_ph, mob_no, acct_no, emp_id, pncd.

Columns to analyse: {json.dumps(samples)}

Past PII patterns we have seen before:
{memory_context}

Return JSON only:
{{
  "assessments": [
    {{"column": "cust_ph", "is_pii": true, "pii_type": "phone_number",
      "sensitivity": "Confidential", "masking_action": "mask", "reasoning": "abbreviated phone number"}}
  ]
}}"""
        response = call_bedrock(prompt, req.region)
        result   = parse_json_response(response)
        for item in result.get("assessments", []):
            if item.get("is_pii"):
                llm_findings[item["column"]] = {
                    "pii_type":    item.get("pii_type","unknown"),
                    "sensitivity": item.get("sensitivity","Confidential"),
                    "confidence":  "llm",
                    "method":      "llm",
                    "reasoning":   item.get("reasoning",""),
                }

    all_findings = {**regex_findings, **llm_findings}

    # Determine dataset sensitivity tier
    tier = "Public"
    for info in all_findings.values():
        s = info.get("sensitivity", "Public")
        if SENSITIVITY_ORDER.get(s, 0) > SENSITIVITY_ORDER.get(tier, 0):
            tier = s

    restricted_found = any(i["sensitivity"] == "Restricted" for i in all_findings.values())
    logger.info(f"PII found: {len(all_findings)} columns | Tier: {tier} | Restricted: {restricted_found}")

    # Save to RAG memory
    if all_findings:
        memory_text = (
            f"PII scan {datetime.now().date()}: Found {len(all_findings)} PII columns: "
            f"{list(all_findings.keys())}. "
            f"LLM caught abbreviated: {list(llm_findings.keys())}. "
            f"Dataset tier: {tier}."
        )
        memory.save("pii_findings", f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    memory_text, {"tier": tier})

    # Save report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {"agent": "PIIAgent", "timestamp": datetime.now().isoformat(),
              "file": req.file_key, "pii_columns": len(all_findings),
              "dataset_tier": tier, "findings": all_findings}
    with open(f"{OUTPUT_DIR}/pii_scan_{ts}.json", "w") as f:
        json.dump(report, f, indent=2)

    return PIIResponse(status="completed", pii_columns_found=len(all_findings),
                       restricted_columns_found=restricted_found,
                       dataset_sensitivity=tier, findings=all_findings,
                       memory_context=memory_context, timestamp=datetime.now().isoformat())

@app.get("/health")
def health():
    return {"status": "ok", "service": "pii-agent", "timestamp": datetime.now().isoformat()}
