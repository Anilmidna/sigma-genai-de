"""
Ingestion Quality Agent — FastAPI app on port 8004
POST /check-quality → profile → GE rules (versioned in S3) → validate → quarantine → decision
GET  /health        → health check
"""

import json, os, sys
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import (call_bedrock, get_logger, read_s3_json_gz,
                   load_ge_suite, save_ge_suite, parse_json_response)
from agent_memory import AgentMemory

app    = FastAPI(title="Quality Agent", version="1.0")
logger = get_logger("quality-agent")
memory = AgentMemory()

REGION     = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
OUTPUT_DIR = os.getenv("PLATFORM_DIR", os.path.join(os.path.dirname(__file__), "..")) + "/agent_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class QualityRequest(BaseModel):
    bucket:   str
    file_key: str
    region:   str = REGION

class QualityResponse(BaseModel):
    status:          str
    total_rows:      int
    clean_rows:      int
    quarantined_rows:int
    quarantine_pct:  float
    checks_passed:   int
    checks_failed:   int
    load_decision:   str
    memory_context:  str
    ge_suite_source: str
    timestamp:       str

def profile_df(df) -> dict:
    profile = {"columns": {}, "summary": {}}
    for col in df.columns:
        s      = df[col]
        n      = len(s)
        n_null = int(s.isna().sum()) + int((s.astype(str) == "").sum())
        import pandas as pd
        num    = pd.to_numeric(s, errors="coerce")
        cp     = {"null_pct": round(n_null/n*100, 1),
                  "inferred_type": "numeric" if num.notna().sum() > n*0.5 else "string"}
        if cp["inferred_type"] == "numeric":
            cp["min"] = float(num.min()); cp["max"] = float(num.max())
            cp["negative_count"] = int((num < 0).sum())
        else:
            cp["top_values"] = {str(k): int(v) for k, v in s.value_counts().head(3).items()}
        profile["columns"][col] = cp
    profile["summary"] = {
        "total_rows": df.shape[0], "total_columns": df.shape[1],
        "column_names": list(df.columns),
        "completeness_pct": round((1 - df.isnull().sum().sum()/(df.shape[0]*df.shape[1]))*100, 1),
    }
    return profile

def run_checks(df, expectations) -> list:
    import pandas as pd
    results = []
    for exp in expectations:
        col   = exp.get("kwargs", {}).get("column")
        etype = exp.get("expectation_type", "")
        r     = {"expectation": etype, "column": col,
                 "severity": exp.get("severity"), "passed": True, "failed_indices": []}
        try:
            if etype == "expect_column_values_to_not_be_null":
                mask = df[col].isna() | (df[col].astype(str).str.strip() == "")
                r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_be_between":
                num  = pd.to_numeric(df[col], errors="coerce")
                lo   = exp["kwargs"].get("min_value", float("-inf"))
                hi   = exp["kwargs"].get("max_value", float("inf"))
                mask = (num < lo) | (num > hi) | num.isna()
                r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_be_in_set":
                val_set = set(exp["kwargs"].get("value_set", []))
                if val_set:
                    mask = ~df[col].astype(str).isin(val_set)
                    r["failed_indices"] = df[mask].index.tolist()
            elif etype == "expect_column_values_to_match_regex":
                pattern = exp["kwargs"].get("regex", ".*")
                mask    = ~df[col].astype(str).str.match(pattern)
                r["failed_indices"] = df[mask].index.tolist()
        except KeyError:
            r["error"] = f"Column '{col}' not found"
        r["failed_count"] = len(r["failed_indices"])
        r["passed"]       = r["failed_count"] == 0
        results.append(r)
    return results

@app.post("/check-quality", response_model=QualityResponse)
async def check_quality_endpoint(req: QualityRequest):
    import pandas as pd
    logger.info(f"Quality check: {req.file_key}")

    rows    = read_s3_json_gz(req.bucket, req.file_key, req.region)
    df      = pd.DataFrame(rows)
    profile = profile_df(df)
    logger.info(f"Rows: {profile['summary']['total_rows']} | "
                f"Completeness: {profile['summary']['completeness_pct']}%")

    # GE Suite: load from S3 if exists (versioned) else generate with LLM
    suite_name = "sigma_transactions_v1"
    ge_suite   = load_ge_suite(req.bucket, suite_name, req.region)
    ge_source  = "s3_versioned"

    if not ge_suite:
        logger.info("No existing GE suite. Generating with Bedrock Nova Pro...")

        # RAG: retrieve past quality issues before generating rules
        past_issues = memory.retrieve("quality_issues",
                                      "data quality rules transactions", n_results=2)
        memory_context = "\n".join(past_issues) if past_issues else "No past issues retrieved"

        prompt = f"""You are a data quality engineer at Sigma DataTech (fintech).
Generate a Great Expectations suite for transaction data.

Profile: {json.dumps(profile, indent=2)}

Past quality issues seen before:
{memory_context}

Generate at least 8 expectations. Return JSON only:
{{
  "expectation_suite_name": "sigma_transactions_v1",
  "expectations": [
    {{"expectation_type": "expect_column_values_to_not_be_null",
      "kwargs": {{"column": "transaction_id"}},
      "severity": "critical", "auto_fixable": false}}
  ]
}}"""
        response = call_bedrock(prompt, req.region)
        ge_suite = parse_json_response(response)
        if not ge_suite:
            ge_suite = {"expectation_suite_name": suite_name, "expectations": [
                {"expectation_type": "expect_column_values_to_not_be_null",
                 "kwargs": {"column": "transaction_id"}, "severity": "critical"},
                {"expectation_type": "expect_column_values_to_be_between",
                 "kwargs": {"column": "amount", "min_value": 0, "max_value": 5000000},
                 "severity": "high"},
                {"expectation_type": "expect_column_values_to_be_in_set",
                 "kwargs": {"column": "currency", "value_set": ["INR","USD","EUR","GBP"]},
                 "severity": "medium"},
                {"expectation_type": "expect_column_values_to_be_in_set",
                 "kwargs": {"column": "status", "value_set": ["completed","pending","failed"]},
                 "severity": "medium"},
            ]}
        # Save to S3 for reuse (production fix: version the suite)
        save_ge_suite(req.bucket, suite_name, ge_suite, req.region)
        ge_source = "llm_generated_and_versioned"
        logger.info(f"GE suite generated and saved to S3 as {suite_name}")
    else:
        memory_context = "GE suite loaded from S3 (versioned)"
        logger.info(f"Using versioned GE suite from S3: {suite_name}")

    n_exp = len(ge_suite.get("expectations", []))

    # Run checks
    check_results = run_checks(df, ge_suite.get("expectations", []))
    passed = sum(1 for r in check_results if r["passed"])
    failed = len(check_results) - passed
    logger.info(f"Checks: {len(check_results)} | Passed: {passed} | Failed: {failed}")

    # Quarantine critical failures
    critical_idx  = set()
    for r in check_results:
        if r.get("severity") == "critical":
            critical_idx.update(r["failed_indices"])

    df_quarantine = df.loc[list(critical_idx)].copy() if critical_idx else pd.DataFrame()
    df_clean      = df.loc[[i for i in df.index if i not in critical_idx]].copy()
    q_pct         = round(len(df_quarantine) / len(df) * 100, 1) if len(df) > 0 else 0

    # Load decision
    if q_pct > 20:     load_decision = "reject_all"
    elif failed > 0:   load_decision = "quarantine_and_load"
    else:              load_decision = "load_clean"

    # Save to RAG memory
    issue_text = (
        f"Quality check {datetime.now().date()}: "
        f"{failed} checks failed, {q_pct}% quarantined. "
        f"Decision: {load_decision}. "
        f"Key issues: {[r['column'] for r in check_results if not r['passed']]}"
    )
    memory.save("quality_issues", f"check_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                issue_text, {"quarantine_pct": q_pct, "load_decision": load_decision})

    # Save quarantine CSV + report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not df_quarantine.empty:
        df_quarantine.to_csv(f"{OUTPUT_DIR}/quarantine_{ts}.csv", index=False)
    report = {"agent": "QualityAgent", "timestamp": datetime.now().isoformat(),
              "file": req.file_key, "total_rows": len(df),
              "clean_rows": len(df_clean), "quarantined_rows": len(df_quarantine),
              "quarantine_pct": q_pct, "load_decision": load_decision,
              "ge_suite_source": ge_source,
              "checks_passed": passed, "checks_failed": failed}
    with open(f"{OUTPUT_DIR}/quality_report_{ts}.json", "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Decision: {load_decision} | Clean: {len(df_clean)} | Quarantined: {len(df_quarantine)}")
    return QualityResponse(status="completed", total_rows=len(df),
                           clean_rows=len(df_clean), quarantined_rows=len(df_quarantine),
                           quarantine_pct=q_pct, checks_passed=passed, checks_failed=failed,
                           load_decision=load_decision, memory_context=memory_context,
                           ge_suite_source=ge_source, timestamp=datetime.now().isoformat())

@app.get("/health")
def health():
    return {"status": "ok", "service": "quality-agent", "timestamp": datetime.now().isoformat()}
