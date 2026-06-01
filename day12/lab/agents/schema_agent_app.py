"""
Schema Evolution Agent — FastAPI app on port 8002
POST /detect-drift  → detects schema changes, generates remediation, saves to RAG memory
GET  /health        → health check
"""

import json, os, re, sys
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import call_bedrock, get_logger, get_latest_s3_file, read_s3_json_gz, parse_json_response
from agent_memory import AgentMemory

app    = FastAPI(title="Schema Evolution Agent", version="1.0")
logger = get_logger("schema-agent")
memory = AgentMemory()

REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
OUTPUT_DIR = os.getenv("PLATFORM_DIR", os.path.join(os.path.dirname(__file__), "..")) + "/agent_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

BASELINE_SCHEMA = {
    "transaction_id": "STRING", "merchant_name": "STRING", "category": "STRING",
    "amount": "DOUBLE", "currency": "STRING", "transaction_date": "DATE",
    "status": "STRING", "customer_id": "STRING",
    "payment_method": "STRING", "merchant_city": "STRING",
}

class DriftRequest(BaseModel):
    bucket:   str
    file_key: str
    region:   str = REGION

class DriftResponse(BaseModel):
    status:         str
    drift_detected: bool
    drift_details:  dict
    remediation:    dict
    memory_context: str
    timestamp:      str

def detect_drift(new_columns: list) -> dict:
    baseline = set(BASELINE_SCHEMA.keys())
    new_cols = set(new_columns)
    added    = new_cols - baseline
    removed  = baseline - new_cols
    renamed  = {}
    for old in list(removed):
        for new in list(added):
            if old[:4].lower() == new[:4].lower():
                renamed[new] = old
                added.discard(new)
                removed.discard(old)
    return {
        "added": list(added), "removed": list(removed),
        "renamed": renamed, "has_drift": bool(added or removed or renamed),
    }

@app.post("/detect-drift", response_model=DriftResponse)
async def detect_drift_endpoint(req: DriftRequest):
    logger.info(f"Scanning file: {req.file_key}")

    # Read S3 file
    rows     = read_s3_json_gz(req.bucket, req.file_key, req.region)
    new_cols = list(rows[0].keys()) if rows else []
    drift    = detect_drift(new_cols)

    if not drift["has_drift"]:
        logger.info("No drift detected")
        return DriftResponse(status="clean", drift_detected=False, drift_details=drift,
                             remediation={}, memory_context="No past incidents retrieved",
                             timestamp=datetime.now().isoformat())

    logger.info(f"Drift detected: {drift}")

    # RAG: retrieve past similar incidents before calling LLM
    query         = f"schema drift {drift['added']} {drift['renamed']}"
    past_incidents = memory.retrieve("schema_drift", query, n_results=2)
    memory_context = "\n".join(past_incidents) if past_incidents else "No similar past incidents found"
    logger.info(f"RAG retrieved {len(past_incidents)} past incident(s)")

    # Call Bedrock with past context
    prompt = f"""You are a senior data engineer at Sigma DataTech.

Schema drift detected in the Kinesis → S3 pipeline.
Baseline columns: {list(BASELINE_SCHEMA.keys())}
New columns in file: {new_cols}
Drift: {json.dumps(drift)}

Past similar incidents (from agent memory):
{memory_context}

Generate remediation. Return JSON only:
{{
  "alter_statements": ["ALTER TABLE sigma.silver.transactions ADD COLUMN upi_ref_id STRING;"],
  "column_mapping": {{"merchant_nm": "merchant_name"}},
  "pyspark_fix": "df = df.withColumn('merchant_name', coalesce(col('merchant_name'), col('merchant_nm')))",
  "risk_level": "medium",
  "risk_reason": "one sentence",
  "recommended_action": "one sentence"
}}"""

    response    = call_bedrock(prompt, req.region)
    remediation = parse_json_response(response)
    if not remediation:
        remediation = {
            "alter_statements": [f"ALTER TABLE sigma.silver.transactions ADD COLUMN {c} STRING;" for c in drift["added"]],
            "column_mapping":   drift["renamed"],
            "pyspark_fix":      "df = df.withColumn('merchant_name', coalesce(col('merchant_name'), col('merchant_nm')))",
            "risk_level":       "medium",
            "risk_reason":      "Renamed column breaks downstream transforms",
            "recommended_action": "Apply ALTER and update Silver transform",
        }

    # Save to RAG memory for future runs
    incident_text = (
        f"Schema drift incident {datetime.now().date()}: "
        f"Added={drift['added']}, Renamed={drift['renamed']}. "
        f"Fix: {remediation.get('recommended_action','')}. "
        f"Risk: {remediation.get('risk_level','')}."
    )
    memory.save("schema_drift", f"incident_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                incident_text, {"drift_type": "column_rename_and_add"})
    logger.info("Incident saved to RAG memory")

    # Save report
    report = {"agent": "SchemaEvolutionAgent", "timestamp": datetime.now().isoformat(),
              "file": req.file_key, "drift_detected": True, "drift": drift,
              "remediation": remediation, "memory_context_used": len(past_incidents) > 0}
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"{OUTPUT_DIR}/schema_drift_incident_{ts}.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Remediation: {remediation.get('recommended_action','')}")
    return DriftResponse(status="drift_detected", drift_detected=True, drift_details=drift,
                         remediation=remediation, memory_context=memory_context,
                         timestamp=datetime.now().isoformat())

@app.get("/health")
def health():
    return {"status": "ok", "service": "schema-agent", "timestamp": datetime.now().isoformat()}
