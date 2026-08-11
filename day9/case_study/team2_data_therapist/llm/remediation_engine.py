"""
Remediation Engine — Round 2
Uses Nova Lite to prescribe fixes for each diagnosed issue.
Includes mandatory side-effect warnings — especially for the dangerous "negative → positive" fix.
"""

import json

from llm.bedrock_client import call_nova_lite, BEDROCK_AVAILABLE


# ── Fallback mocked prescriptions ────────────────────────────────────────────
MOCK_PRESCRIPTIONS = {
    "DX001": {
        "issue_id": "DX001",
        "recommended_fix": "Deduplicate records using transaction_id as the key, keeping the record with the latest transaction_timestamp (assuming the latest is the authoritative retry).",
        "sql_fix": """-- Deduplicate: keep latest record per transaction_id
CREATE TABLE silver_transactions AS
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY transaction_id
        ORDER BY transaction_timestamp DESC
    ) AS rn
    FROM bronze_transactions
    WHERE transaction_id IS NOT NULL
) WHERE rn = 1;""",
        "python_fix": """df = df.sort_values('transaction_timestamp', ascending=False)
df = df.dropna(subset=['transaction_id'])
df = df.drop_duplicates(subset=['transaction_id'], keep='first')""",
        "explanation": "Deduplication via window function preserves the most recent version of each transaction. NULL transaction IDs are excluded first to prevent joining issues.",
        "side_effect_warning": "⚠️ If the source system intentionally sends retry transactions with a different amount (e.g., partial authorization), keeping only the latest will silently discard the authoritative original.",
        "downstream_risk": "Could remove legitimate correction transactions that arrived later with updated amounts.",
        "confidence_level": 90,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX002": {
        "issue_id": "DX002",
        "recommended_fix": "Fill NULL merchant_name values with the placeholder 'UNKNOWN' to maintain referential integrity in Silver.",
        "sql_fix": """UPDATE bronze_transactions
SET merchant_name = 'UNKNOWN'
WHERE merchant_name IS NULL;""",
        "python_fix": """df['merchant_name'] = df['merchant_name'].fillna('UNKNOWN')""",
        "explanation": "Filling with UNKNOWN ensures these records are not dropped from Silver but are clearly marked for investigation. Downstream systems can filter or flag UNKNOWN merchants.",
        "side_effect_warning": "⚠️ Merchant-level analytics will now include an 'UNKNOWN' category that inflates ambiguity in revenue reports and merchant performance dashboards.",
        "downstream_risk": "Finance reports may show unexplained revenue under 'UNKNOWN' merchant. Merchant SLAs cannot be measured for these records.",
        "confidence_level": 83,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX003": {
        "issue_id": "DX003",
        "recommended_fix": "Convert all negative transaction amounts to their absolute positive values using ABS().",
        "sql_fix": """-- ⚠️ DANGEROUS: This converts ALL negatives — including legitimate REFUNDS
UPDATE bronze_transactions
SET transaction_amount = ABS(transaction_amount)
WHERE transaction_amount < 0;""",
        "python_fix": """# ⚠️ DANGEROUS: This flips refund amounts to positive
df['transaction_amount'] = df['transaction_amount'].abs()""",
        "explanation": "Negative amounts violate typical accounting conventions in OLAP systems. Converting to ABS() makes the data 'look' cleaner and reduces null/negative validation failures.",
        "side_effect_warning": "🚨 CRITICAL SIDE EFFECT: This fix will ALSO convert legitimate REFUND transactions (which are correctly negative) to positive values. A ₹-500 refund becomes ₹+500 in the Silver layer, turning a refund into a purchase in downstream aggregates.",
        "downstream_risk": "Revenue totals will be INFLATED. Refund metrics will show ₹0 refunds. Finance dashboards will show double revenue. Chargeback models will miss negative signal.",
        "confidence_level": 71,
        "is_dangerous": True,
        "danger_reason": "Flips legitimate REFUND records from negative to positive, corrupting refund accounting and inflating revenue totals downstream.",
    },
    "DX004": {
        "issue_id": "DX004",
        "recommended_fix": "Filter out rows with timestamps that are syntactically invalid, logically impossible (future dates > 2030), or epoch-zero.",
        "sql_fix": """-- Remove rows with bad timestamps
CREATE TABLE silver_transactions AS
SELECT * FROM bronze_transactions
WHERE transaction_timestamp NOT IN ('not-a-date', '0000-00-00 00:00:00', '2024-13-45 00:00:00')
  AND CAST(SPLIT_PART(transaction_timestamp, '-', 1) AS INTEGER) <= 2030;""",
        "python_fix": """bad_ts = ['not-a-date', '0000-00-00 00:00:00', '2024-13-45 00:00:00']
df = df[~df['transaction_timestamp'].isin(bad_ts)]
df = df[df['transaction_timestamp'].str[:4].astype(int) <= 2030]""",
        "explanation": "Rows with impossible timestamps cannot be reliably used in time-series analysis, SLA monitoring, or fraud temporal detection. Removal is safer than imputation.",
        "side_effect_warning": "⚠️ If the '2099-12-31' timestamp is a sentinel value used by SYS_C to indicate 'open/pending' transactions, removing it will silently drop valid in-flight transactions.",
        "downstream_risk": "Pending transaction queue may lose records, causing SLA breaches to go undetected.",
        "confidence_level": 94,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX005": {
        "issue_id": "DX005",
        "recommended_fix": "Fill NULL customer_id values with 'UNKNOWN_CUST' placeholder to preserve the record in Silver while flagging for investigation.",
        "sql_fix": """UPDATE bronze_transactions
SET customer_id = 'UNKNOWN_CUST'
WHERE customer_id IS NULL;""",
        "python_fix": """df['customer_id'] = df['customer_id'].fillna('UNKNOWN_CUST')""",
        "explanation": "Guest or unauthenticated transactions are valid business events and should not be dropped. Using a placeholder preserves revenue tracking while clearly marking unresolvable customer links.",
        "side_effect_warning": "⚠️ All UNKNOWN_CUST records will be grouped together in customer analytics, artificially creating a single 'super-customer' with combined spend from all guest transactions.",
        "downstream_risk": "CLV models will have a distorted UNKNOWN_CUST entity. Churn prediction will be unreliable for guest transactions.",
        "confidence_level": 79,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX006": {
        "issue_id": "DX006",
        "recommended_fix": "Recode all non-standard transaction_type values to 'UNKNOWN' to maintain referential integrity while flagging for source system remediation.",
        "sql_fix": """UPDATE bronze_transactions
SET transaction_type = 'UNKNOWN'
WHERE transaction_type NOT IN ('PURCHASE', 'REFUND', 'CHARGEBACK', 'TRANSFER');""",
        "python_fix": """valid_types = ['PURCHASE', 'REFUND', 'CHARGEBACK', 'TRANSFER']
df['transaction_type'] = df['transaction_type'].apply(
    lambda x: x if x in valid_types else 'UNKNOWN'
)""",
        "explanation": "Standardizing transaction types to the canonical taxonomy ensures downstream models, dashboards, and routing logic function correctly.",
        "side_effect_warning": "⚠️ 'CANCELLED' records recoded as 'UNKNOWN' may be incorrectly included in revenue totals if downstream logic only filters on status, not type.",
        "downstream_risk": "Type-based business logic may misclassify these transactions. The real fix should be a source-system mapping table, not a one-size-fits-all recode.",
        "confidence_level": 85,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX007": {
        "issue_id": "DX007",
        "recommended_fix": "Remove records with transaction_amount > ₹100,000 and route them to a separate 'high_value_review' table for human investigation.",
        "sql_fix": """-- Remove outliers from main Silver flow
CREATE TABLE silver_transactions AS
SELECT * FROM bronze_transactions
WHERE transaction_amount <= 100000;

-- Route outliers to review queue
CREATE TABLE high_value_review AS
SELECT * FROM bronze_transactions
WHERE transaction_amount > 100000;""",
        "python_fix": """df_silver = df[df['transaction_amount'] <= 100000]
df_outliers = df[df['transaction_amount'] > 100000]""",
        "explanation": "Extreme outliers skew statistical models and revenue reporting. Routing to a review queue ensures human oversight without data loss.",
        "side_effect_warning": "⚠️ If any of the high-value transactions are legitimate enterprise B2B transfers, removing them will cause underreported enterprise revenue for the period.",
        "downstream_risk": "Enterprise segment revenue will be artificially suppressed. Merchant GMV for high-value categories will be understated.",
        "confidence_level": 76,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX008": {
        "issue_id": "DX008",
        "recommended_fix": "Apply TRIM() to all merchant_name values to remove leading and trailing whitespace.",
        "sql_fix": """UPDATE bronze_transactions
SET merchant_name = TRIM(merchant_name)
WHERE merchant_name IS NOT NULL;""",
        "python_fix": """df['merchant_name'] = df['merchant_name'].str.strip()""",
        "explanation": "Whitespace normalization is a safe, low-risk operation that prevents silent grouping failures in SQL analytics and dashboard tools.",
        "side_effect_warning": "✅ This fix has minimal side effects. Trimming whitespace is safe for all downstream operations.",
        "downstream_risk": "No significant downstream risk identified.",
        "confidence_level": 99,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX009": {
        "issue_id": "DX009",
        "recommended_fix": "Remove records with invalid source_system codes not in the registered system registry (SYS_A, SYS_B, SYS_C).",
        "sql_fix": """CREATE TABLE silver_transactions AS
SELECT * FROM bronze_transactions
WHERE source_system IN ('SYS_A', 'SYS_B', 'SYS_C');""",
        "python_fix": """df = df[df['source_system'].isin(['SYS_A', 'SYS_B', 'SYS_C'])]""",
        "explanation": "Transactions from unregistered source systems cannot be reliably audited, traced, or included in SLA metrics. Removal preserves data lineage integrity.",
        "side_effect_warning": "⚠️ If a legitimate new partner was added but their source system code was not yet registered, their transactions will be silently dropped from Silver.",
        "downstream_risk": "New partner revenue may go unaccounted for a reporting cycle. Partner onboarding SLAs will be missed.",
        "confidence_level": 82,
        "is_dangerous": False,
        "danger_reason": None,
    },
    "DX010": {
        "issue_id": "DX010",
        "recommended_fix": "Remove all records where transaction_id is NULL, as they cannot be keyed, deduplicated, or joined in Silver.",
        "sql_fix": """CREATE TABLE silver_transactions AS
SELECT * FROM bronze_transactions
WHERE transaction_id IS NOT NULL;""",
        "python_fix": """df = df.dropna(subset=['transaction_id'])""",
        "explanation": "NULL transaction IDs are fundamentally unresolvable without source system re-ingestion. They cannot serve as primary keys in Silver and break all downstream joins.",
        "side_effect_warning": "⚠️ If any of the NULL-ID records represent legitimate high-value transactions, their revenue will be permanently lost from Silver reporting.",
        "downstream_risk": "Revenue from NULL-ID transactions will not be reflected in Silver or Gold layer reports.",
        "confidence_level": 93,
        "is_dangerous": False,
        "danger_reason": None,
    },
}


def build_prescription_prompt(diagnosis: dict) -> tuple:
    """Build Nova Lite prompt for a single issue prescription."""
    system_prompt = """You are an expert Data Engineer at Sigma DataTech.
Your job is to prescribe specific, actionable fixes for data quality issues diagnosed in the Bronze layer.
You MUST be honest about side effects and downstream risks — especially when a fix could corrupt business logic.
Respond in valid JSON format with the exact schema specified."""

    user_prompt = f"""Prescribe a specific remediation for this data quality issue:

DIAGNOSIS:
- Issue ID: {diagnosis.get('issue_id')}
- Issue: {diagnosis.get('issue_title')}
- Description: {diagnosis.get('issue_description')}
- Severity: {diagnosis.get('severity')}
- Root Cause: {diagnosis.get('root_cause_hypothesis')}
- Affected Rows: {diagnosis.get('affected_rows_estimate')}
- Business Impact: {diagnosis.get('business_impact')}

Return a JSON object with these EXACT fields:
- issue_id: string
- recommended_fix: string (clear, actionable description)
- sql_fix: string (valid DuckDB SQL)
- python_fix: string (pandas code)
- explanation: string (why this fix works)
- side_effect_warning: string (what could go wrong — be brutally honest)
- downstream_risk: string (business impact if fix is wrong)
- confidence_level: integer (0-100)
- is_dangerous: boolean (true if this fix could corrupt downstream business logic)
- danger_reason: string or null (explain the danger if is_dangerous is true)

Return ONLY valid JSON. No markdown, no preamble."""

    return system_prompt, user_prompt


def run_prescriptions(diagnoses: list) -> dict:
    """
    Run AI prescriptions using Nova Lite for each diagnosed issue.
    Returns dict keyed by issue_id.
    Falls back to mock if Bedrock unavailable.
    """
    prescriptions = {}

    for diagnosis in diagnoses:
        issue_id = diagnosis.get("issue_id", "")

        if not BEDROCK_AVAILABLE:
            prescriptions[issue_id] = MOCK_PRESCRIPTIONS.get(issue_id, {})
            continue

        try:
            system_prompt, user_prompt = build_prescription_prompt(diagnosis)
            response_text = call_nova_lite(system=system_prompt, user=user_prompt, max_tokens=1200)

            text = response_text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])

            prescription = json.loads(text)
            prescriptions[issue_id] = prescription

        except Exception as e:
            print(f"[WARN] Prescription failed for {issue_id}: {e}. Using mock.")
            prescriptions[issue_id] = MOCK_PRESCRIPTIONS.get(issue_id, {})

    return prescriptions
