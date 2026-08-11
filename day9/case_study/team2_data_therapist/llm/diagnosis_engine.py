"""
Diagnosis Engine — Round 1
Uses Nova Pro to diagnose data quality issues in the Bronze layer.
"""

import json

from llm.bedrock_client import call_nova_pro, BEDROCK_AVAILABLE


# ── Fallback mocked diagnoses ─────────────────────────────────────────────────
MOCK_DIAGNOSES = [
    {
        "issue_id": "DX001",
        "issue_title": "Duplicate Transaction IDs",
        "issue_description": "Multiple rows share the same transaction_id, indicating ingestion retries or Kafka message replay events from Source System B.",
        "severity": "HIGH",
        "root_cause_hypothesis": "Kafka consumer offset reset or pipeline retry logic in SYS_B caused the same events to be re-published. The ingestion layer lacks idempotency checks.",
        "confidence_score": 92,
        "affected_rows_estimate": 10,
        "business_impact": "Revenue duplication in downstream aggregates. Finance dashboards will show inflated GMV. Fraud models will double-count suspicious transactions.",
        "fix_key": "fix_duplicates",
    },
    {
        "issue_id": "DX002",
        "issue_title": "Null Merchant Names",
        "issue_description": "Approximately 8 records have NULL merchant_name. These originate from SYS_C which sends an incomplete payload when the merchant lookup service times out.",
        "severity": "MEDIUM",
        "root_cause_hypothesis": "Merchant enrichment service in SYS_C has a 30-second timeout. When latency spikes, the merchant join is skipped and NULL is written instead of failing gracefully.",
        "confidence_score": 85,
        "affected_rows_estimate": 8,
        "business_impact": "Merchant-level analytics, GMV attribution and regional performance reports will have unaccounted revenue. Compliance reports may flag missing merchant data.",
        "fix_key": "fix_null_merchant",
    },
    {
        "issue_id": "DX003",
        "issue_title": "Negative Transaction Amounts (Non-Refund Records)",
        "issue_description": "Several records show negative amounts but are NOT tagged as REFUND type. This is inconsistent. However, some negative values are legitimate refunds.",
        "severity": "HIGH",
        "root_cause_hypothesis": "SYS_A sends refund adjustments without updating the transaction_type field. The sign of the amount is the only indicator of a refund in that source system.",
        "confidence_score": 88,
        "affected_rows_estimate": 6,
        "business_impact": "Revenue calculations will subtract these amounts incorrectly. Converting them blindly to positive values WILL corrupt refund accounting downstream.",
        "fix_key": "fix_negative_amounts",
    },
    {
        "issue_id": "DX004",
        "issue_title": "Malformed & Impossible Timestamps",
        "issue_description": "4 records have timestamps that are either syntactically invalid ('not-a-date'), logically impossible (year 2099, month 13), or epoch-zero (0000-00-00).",
        "severity": "HIGH",
        "root_cause_hypothesis": "SYS_C uses an undocumented date format and has no timestamp validation at the source. The pipeline ingests without schema enforcement.",
        "confidence_score": 96,
        "affected_rows_estimate": 4,
        "business_impact": "Time-series analytics, SLA monitoring, and fraud temporal models will fail or produce incorrect results. Year 2099 records will appear as far-future anomalies.",
        "fix_key": "fix_bad_timestamps",
    },
    {
        "issue_id": "DX005",
        "issue_title": "Missing Customer IDs",
        "issue_description": "7 records have NULL customer_id. These are transactions where the user was not authenticated or the session token expired before the transaction completed.",
        "severity": "MEDIUM",
        "root_cause_hypothesis": "Guest checkout flow in SYS_B does not mandate customer registration. The pipeline treats guest transactions identically to registered customer transactions.",
        "confidence_score": 80,
        "affected_rows_estimate": 7,
        "business_impact": "Customer lifetime value (CLV) calculations will miss revenue. Loyalty programs, cohort analysis, and personalization models will lose data fidelity.",
        "fix_key": "fix_null_customer_id",
    },
    {
        "issue_id": "DX006",
        "issue_title": "Invalid Transaction Types",
        "issue_description": "5 records use non-standard transaction type codes (APPROVED, CANCELLED, VOID, RETRY) that are not part of the official Sigma DataTech taxonomy.",
        "severity": "MEDIUM",
        "root_cause_hypothesis": "SYS_A uses a legacy internal taxonomy from a 2021 migration that was never aligned with Sigma's canonical data model. No schema validation exists at ingestion.",
        "confidence_score": 90,
        "affected_rows_estimate": 5,
        "business_impact": "Transaction type-based routing, reporting, and ML feature engineering will produce incorrect results or silently drop records filtered by type.",
        "fix_key": "fix_invalid_types",
    },
    {
        "issue_id": "DX007",
        "issue_title": "Extreme Outlier Amounts (Possible Fraud Signals)",
        "issue_description": "3 records show transaction amounts between ₹5,00,000 and ₹20,00,000 — 40-400x above the 99th percentile of normal transactions.",
        "severity": "HIGH",
        "root_cause_hypothesis": "These could be legitimate high-value B2B transfers, data entry errors (extra zeros), or adversarial fraud probes. The source system has no upper-bound validation.",
        "confidence_score": 78,
        "affected_rows_estimate": 3,
        "business_impact": "Revenue aggregates will be massively skewed. Fraud detection models trained on this data will learn incorrect amount distributions.",
        "fix_key": "fix_outliers",
    },
    {
        "issue_id": "DX008",
        "issue_title": "Whitespace Contamination in Merchant Names",
        "issue_description": "5 merchant name fields have leading/trailing whitespace (e.g., '  Amazon  '). This causes GROUP BY and JOIN operations to fail silently.",
        "severity": "LOW",
        "root_cause_hypothesis": "The SYS_B web form does not strip whitespace from merchant name input fields. Merchant names are stored raw from form submissions.",
        "confidence_score": 99,
        "affected_rows_estimate": 5,
        "business_impact": "Merchant-level aggregations will split the same merchant into multiple records. Dashboards will show 'Amazon' and '  Amazon  ' as different merchants.",
        "fix_key": "fix_whitespace",
    },
    {
        "issue_id": "DX009",
        "issue_title": "Invalid Source System Codes",
        "issue_description": "4 records have source_system values not in the known system registry (SYS_A, SYS_B, SYS_C). Values include SYS_X, UNKNOWN, and empty strings.",
        "severity": "MEDIUM",
        "root_cause_hypothesis": "A new partner integration was tested directly in production without registering the source system in the platform registry. Test data leaked into Bronze.",
        "confidence_score": 87,
        "affected_rows_estimate": 4,
        "business_impact": "Data lineage and auditability are compromised. Source-system-level quality SLAs cannot be measured for these records.",
        "fix_key": "fix_invalid_source",
    },
    {
        "issue_id": "DX010",
        "issue_title": "Null Transaction IDs",
        "issue_description": "4 records have no transaction_id, making them impossible to deduplicate, join, or track across systems.",
        "severity": "HIGH",
        "root_cause_hypothesis": "SYS_C generates IDs asynchronously after the transaction record is written. A race condition causes some records to be flushed before the ID is assigned.",
        "confidence_score": 91,
        "affected_rows_estimate": 4,
        "business_impact": "These records cannot be deduped, cannot be primary-keyed in Silver, and create referential integrity failures in downstream Gold layer joins.",
        "fix_key": "fix_null_txn_id",
    },
]


def build_diagnosis_prompt(stats: dict) -> tuple:
    """Build Nova Pro prompt for diagnosis."""
    system_prompt = """You are an expert enterprise Data Quality Analyst at Sigma DataTech.
You analyze raw Bronze-layer transaction data and produce structured diagnoses.
Your responses must be precise, technical, enterprise-grade, and actionable.
Always respond in valid JSON array format with the exact schema specified.
Focus on root cause analysis, business impact, and data engineering insights."""

    user_prompt = f"""Analyze the following Bronze-layer transaction dataset statistics and diagnose all data quality issues.

DATASET STATISTICS:
- Total rows: {stats.get('total_rows', 0)}
- Null transaction IDs: {stats.get('null_transaction_id', 0)}
- Null customer IDs: {stats.get('null_customer_id', 0)}
- Null merchant names: {stats.get('null_merchant', 0)}
- Duplicate transaction IDs: {stats.get('duplicate_ids', 0)} groups
- Negative amounts: {stats.get('negative_amounts', 0)}
- Bad/impossible timestamps: {stats.get('bad_timestamps', 0)}
- Invalid transaction types: {stats.get('invalid_types', 0)}
- Outlier amounts (>100k): {stats.get('outlier_amounts', 0)}
- Whitespace in merchant names: {stats.get('whitespace_merchants', 0)}
- Invalid source systems: {stats.get('invalid_source_systems', 0)}

For each issue, produce a JSON object with these exact fields:
- issue_id: string (DX001, DX002, ...)
- issue_title: string
- issue_description: string (2-3 sentences, technical)
- severity: "HIGH" | "MEDIUM" | "LOW"
- root_cause_hypothesis: string (enterprise root cause reasoning)
- confidence_score: integer (0-100)
- affected_rows_estimate: integer
- business_impact: string (financial/operational impact)

Return ONLY a JSON array. No preamble, no markdown, no explanation outside the JSON."""

    return system_prompt, user_prompt


def run_diagnosis(stats: dict) -> list:
    """
    Run AI diagnosis using Nova Pro.
    Falls back to mock if Bedrock is unavailable.
    """
    if not BEDROCK_AVAILABLE:
        return MOCK_DIAGNOSES

    try:
        system_prompt, user_prompt = build_diagnosis_prompt(stats)
        response_text = call_nova_pro(system=system_prompt, user=user_prompt, max_tokens=2000)

        # Parse JSON response
        # Strip markdown fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])

        diagnoses = json.loads(text)

        # Attach fix_keys to match our known issues
        fix_key_map = {
            "DX001": "fix_duplicates",
            "DX002": "fix_null_merchant",
            "DX003": "fix_negative_amounts",
            "DX004": "fix_bad_timestamps",
            "DX005": "fix_null_customer_id",
            "DX006": "fix_invalid_types",
            "DX007": "fix_outliers",
            "DX008": "fix_whitespace",
            "DX009": "fix_invalid_source",
            "DX010": "fix_null_txn_id",
        }
        for d in diagnoses:
            d["fix_key"] = fix_key_map.get(d.get("issue_id", ""), "")

        return diagnoses

    except Exception as e:
        # Graceful fallback to mock
        print(f"[WARN] Bedrock call failed: {e}. Using mock diagnoses.")
        return MOCK_DIAGNOSES
