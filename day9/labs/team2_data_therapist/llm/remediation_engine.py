"""
AI Remediation Engine using AWS Bedrock Nova Lite.
Generates code-level prescriptions, SQL scripts, warnings, and safety risk profiles for detected data quality issues.
Includes the pre-seeded "Negative Amount ABS()" trap as part of its core recommendation schema.
"""

import json
import boto3

# Pre-seeded remediation catalog, which matches the issues detected in diagnosis_engine.py.
# Includes the key trap: negative amounts should be converted to positive (absolute value) as a naive AI recommendation.
MOCK_REMEDIATION_REPORT = {
    "duplicates": {
        "recommended_fix": "Deduplicate by transaction_id and retain only the latest record based on transaction_timestamp.",
        "sql_fix": """WITH ranked AS (
    SELECT transaction_id, transaction_timestamp,
           row_number() OVER (PARTITION BY transaction_id ORDER BY transaction_timestamp DESC) as rn
    FROM silver_transactions
    WHERE transaction_id IS NOT NULL
)
DELETE FROM silver_transactions
WHERE (transaction_id, transaction_timestamp) IN (
    SELECT transaction_id, transaction_timestamp FROM ranked WHERE rn > 1
);""",
        "pandas_fix": "df = df.sort_values('transaction_timestamp', ascending=False).drop_duplicates(subset=['transaction_id'], keep='first')",
        "explanation": "Finds duplicate transaction keys and keeps the most recent state. This resolves ingestion retries while retaining the updated record.",
        "side_effect_warning": "If a customer completes two valid transactions of identical amounts in quick succession, one may be incorrectly discarded.",
        "downstream_risk": "Low risk overall, but could lead to slight revenue under-reporting if transaction IDs are recycled in error.",
        "confidence_level": "95%",
        "is_safe": True
    },
    "null_ids": {
        "recommended_fix": "Purge records where transaction_id is missing/null, as they cannot be keyed or joined.",
        "sql_fix": "DELETE FROM silver_transactions WHERE transaction_id IS NULL;",
        "pandas_fix": "df = df.dropna(subset=['transaction_id'])",
        "explanation": "Removes transactions that completely lack primary identifiers.",
        "side_effect_warning": "Permanently deletes data from the database. Discarded transaction details cannot be recovered from the Silver table.",
        "downstream_risk": "Loss of total transaction count and under-reporting of raw transaction traffic.",
        "confidence_level": "99%",
        "is_safe": True
    },
    "null_merchants": {
        "recommended_fix": "Coalesce null merchant names to standard 'UNKNOWN' placeholder.",
        "sql_fix": "UPDATE silver_transactions SET merchant_name = 'UNKNOWN' WHERE merchant_name IS NULL;",
        "pandas_fix": "df['merchant_name'] = df['merchant_name'].fillna('UNKNOWN')",
        "explanation": "Substitutes missing merchant strings with 'UNKNOWN' to prevent null reference issues in dashboard joins.",
        "side_effect_warning": "Creates a synthetic merchant group called 'UNKNOWN' which acts as a bucket for all failed merchant lookups.",
        "downstream_risk": "Merchant ranking charts will show 'UNKNOWN' as a high-performing merchant, skewing competitive analysis.",
        "confidence_level": "90%",
        "is_safe": True
    },
    "null_customers": {
        "recommended_fix": "Fill missing customer IDs with a default 'GUEST' flag.",
        "sql_fix": "UPDATE silver_transactions SET customer_id = 'GUEST' WHERE customer_id IS NULL;",
        "pandas_fix": "df['customer_id'] = df['customer_id'].fillna('GUEST')",
        "explanation": "Maintains financial transaction lineage by associating empty customer profiles with a generic 'GUEST' customer ID.",
        "side_effect_warning": "Downstream CRM segmentation systems will perceive 'GUEST' as a single customer who makes frequent purchases.",
        "downstream_risk": "Distorts Customer Lifetime Value (CLV) charts and ruins machine learning recommendation models.",
        "confidence_level": "92%",
        "is_safe": True
    },
    "malformed_timestamps": {
        "recommended_fix": "Re-parse slash ('/') and short dash ('DD-MM-YYYY') formats into standard ISO YYYY-MM-DD HH:MM:SS strings.",
        "sql_fix": """UPDATE silver_transactions
SET transaction_timestamp = CASE
    WHEN transaction_timestamp LIKE '%/%' THEN strftime(strptime(transaction_timestamp, '%Y/%m/%d %H:%M'), '%Y-%m-%d %H:%M:%S')
    WHEN transaction_timestamp LIKE '%-%' AND length(transaction_timestamp) = 10 THEN strftime(strptime(transaction_timestamp, '%d-%m-%Y'), '%Y-%m-%d %H:%M:%S')
    ELSE transaction_timestamp
END
WHERE transaction_timestamp NOT LIKE '2099%';""",
        "pandas_fix": "df['transaction_timestamp'] = pd.to_datetime(df['transaction_timestamp'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')",
        "explanation": "Standardizes raw date strings into unified ISO-8601 formatting for unified time series querying.",
        "side_effect_warning": "If dates are formatted as MM/DD vs DD/MM, parsing tools can silently flip months and days, corrupting date records.",
        "downstream_risk": "Can lead to severe sequence and trend miscalculations if dates are parsed with flipped month/day indices.",
        "confidence_level": "90%",
        "is_safe": True
    },
    "future_timestamps": {
        "recommended_fix": "Delete transactions containing impossible future dates (e.g., date is greater than or equal to 2099).",
        "sql_fix": "DELETE FROM silver_transactions WHERE transaction_timestamp >= '2099-01-01';",
        "pandas_fix": "df = df[df['transaction_timestamp'] < '2099-01-01']",
        "explanation": "Removes corrupted timezone placeholders or epoch clock error records set in the future.",
        "side_effect_warning": "Legitimate transactions with minor device time drift or local calibration issues could be permanently deleted.",
        "downstream_risk": "Slight loss of data visibility; however, it keeps dashboard metrics clean from extreme chart scale distortion.",
        "confidence_level": "95%",
        "is_safe": True
    },
    "merchant_spellings": {
        "recommended_fix": "Standardize merchant spellings to clean, capitalized base names using a case mapping function.",
        "sql_fix": """UPDATE silver_transactions
SET merchant_name = CASE
    WHEN upper(trim(merchant_name)) LIKE 'AMAZON%' THEN 'Amazon'
    WHEN upper(trim(merchant_name)) LIKE 'SWIGGY%' THEN 'Swiggy'
    WHEN upper(trim(merchant_name)) LIKE 'ZOMATO%' THEN 'Zomato'
    WHEN upper(trim(merchant_name)) LIKE 'FLIPKART%' THEN 'Flipkart'
    WHEN upper(trim(merchant_name)) LIKE 'NETFLIX%' THEN 'Netflix'
    WHEN upper(trim(merchant_name)) LIKE 'UBER%' THEN 'Uber'
    ELSE trim(merchant_name)
END
WHERE merchant_name IS NOT NULL;""",
        "pandas_fix": """def clean_merch(name):
    if not isinstance(name, str): return name
    n = name.strip().upper()
    for m in ['AMAZON', 'SWIGGY', 'ZOMATO', 'FLIPKART', 'NETFLIX', 'UBER']:
        if m in n: return m.capitalize()
    return name.strip()
df['merchant_name'] = df['merchant_name'].apply(clean_merch)""",
        "explanation": "Collapses spelling variations and corporate suffixes into a singular clean brand catalog.",
        "side_effect_warning": "Could inadvertently merge sub-brands or distinct entities (e.g., merging Amazon Web Services and Amazon.com Retail).",
        "downstream_risk": "Low risk, but potentially groups distinct business lines into a single bucket, masking micro-revenue sources.",
        "confidence_level": "88%",
        "is_safe": True
    },
    "negative_amounts": {
        "recommended_fix": "✨ (RECOMMENDED BY AI) Convert negative amounts to positive by applying absolute values ABS(), assuming a sign-flip database ingestion error.",
        "sql_fix": """-- [DANGEROUS NAIVE AI RECOMMENDATION]
UPDATE silver_transactions
SET transaction_amount = abs(transaction_amount)
WHERE transaction_amount < 0;""",
        "pandas_fix": "df['transaction_amount'] = df['transaction_amount'].abs()",
        "explanation": "Removes negative values from the transaction ledger, standardizing amounts to positive-only figures.",
        "side_effect_warning": "⚠️ ZERO WARNINGS GENERATED. The model indicates this is a clean, 100% safe operation to standardize currency fields.",
        "downstream_risk": "🚨 **CRITICAL RISK:** Naively converting negative values to positive transforms refund/chargeback records into purchase records. Downstream revenue will double incorrectly, and refund records will vanish from accounting dashboards!",
        "confidence_level": "99% (Highly Confident)",
        "is_safe": False  # This is the trap!
    },
    "outliers": {
        "recommended_fix": "Filter out extreme value records where the absolute transaction amount exceeds $100,000.",
        "sql_fix": "DELETE FROM silver_transactions WHERE abs(transaction_amount) > 100000;",
        "pandas_fix": "df = df[df['transaction_amount'].abs() <= 100000]",
        "explanation": "Discards fraudulent inputs or extreme system fat-finger amounts that skew aggregations.",
        "side_effect_warning": "Discards legitimate large institutional or corporate transactions from the metrics entirely.",
        "downstream_risk": "High-value business accounts will look completely inactive on dashboards, which can trigger fake compliance alerts.",
        "confidence_level": "85%",
        "is_safe": True
    }
}

# The Safe human remediation block for negative amounts (to compare in Round 3/What AI Got Wrong)
SAFE_HUMAN_REMEDIATION = {
    "recommended_fix": "🛡️ (SAFE HUMAN REMEDIATION) Keep negative values as adjustments (refunds/chargebacks) but validate and fix the transaction_type flag.",
    "sql_fix": """-- [SAFE HUMAN ALTERNATIVE]
UPDATE silver_transactions
SET transaction_type = CASE 
    WHEN transaction_type NOT IN ('REFUND', 'CHARGEBACK') THEN 'REFUND' 
    ELSE transaction_type 
END
WHERE transaction_amount < 0;""",
    "pandas_fix": "df.loc[df['transaction_amount'] < 0, 'transaction_type'] = df['transaction_type'].apply(lambda x: x if x in ['REFUND', 'CHARGEBACK'] else 'REFUND')",
    "explanation": "Preserves negative signs because refunds are negative adjustments to total revenue. Corrects the transaction_type flag to align with financial ledgers.",
    "side_effect_warning": "Requires downstream logic and dashboards to actively support summing negative amounts rather than expecting only positive integers.",
    "downstream_risk": "None for standard accounting practices. Essential for net revenue reports.",
    "confidence_level": "98%",
    "is_safe": True
}

def prescribe_remediation(issue_id, use_bedrock=False):
    """
    Returns the remediation guidelines for a given issue ID.
    By default, returns pre-configured mock prescriptions to ensure safety, precision, and reliable storytelling.
    If use_bedrock=True, queries AWS Bedrock Nova Lite to generate the suggestion dynamically.
    """
    # For negative_amounts, if not using Bedrock, we return both our naive trap and we make the safe human fix accessible.
    if not use_bedrock:
        if issue_id == "negative_amounts_safe":
            return SAFE_HUMAN_REMEDIATION
        return MOCK_REMEDIATION_REPORT.get(issue_id, {"recommended_fix": "No fix found.", "sql_fix": "-- No fix available"})
        
    try:
        # If Bedrock is requested, let's call Nova Lite
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        
        system_prompt = (
            "You are an expert 'AI Data Therapist' and Senior Data Engineer at Sigma DataTech. "
            "You prescribe clean, professional remediation plans for data quality issues. "
            "Your output must be JSON only. No conversation. "
            "Format the JSON with these fields:\n"
            "- recommended_fix: short description of the remedy\n"
            "- sql_fix: executable DuckDB SQL script to apply the fix against a table called 'silver_transactions'\n"
            "- pandas_fix: Pandas snippet to clean the dataframe\n"
            "- explanation: why this fix is selected\n"
            "- side_effect_warning: warning about immediate pipeline issues\n"
            "- downstream_risk: warning about business dashboards or downstream aggregations\n"
            "- confidence_level: percentage string (e.g. '92%')\n"
        )
        
        user_message = f"Please prescribe a remediation plan for the data quality issue: '{issue_id}'."
        
        body = {
            "messages": [{"role": "user", "content": [{"text": user_message}]}],
            "system": [{"text": system_prompt}],
            "inferenceConfig": {"maxTokens": 1000, "temperature": 0.3},
        }
        
        response = client.invoke_model(
            modelId="amazon.nova-lite-v1:0",
            body=json.dumps(body),
        )
        
        result_text = json.loads(response["body"].read())["output"]["message"]["content"][0]["text"]
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        prescription = json.loads(result_text.strip())
        
        # Override negative_amounts if the LLM didn't fall into the trap (as we want to force the trap for educational simulation purposes!)
        if issue_id == "negative_amounts":
            # Force the trap so the simulator works!
            prescription["recommended_fix"] = "✨ (RECOMMENDED BY AI) Convert negative amounts to positive by applying absolute values ABS(), assuming a sign-flip database ingestion error."
            prescription["sql_fix"] = """-- [DANGEROUS NAIVE AI RECOMMENDATION]
UPDATE silver_transactions
SET transaction_amount = abs(transaction_amount)
WHERE transaction_amount < 0;"""
            prescription["downstream_risk"] = "🚨 **CRITICAL RISK:** Naively converting negative values to positive transforms refund/chargeback records into purchase records. Downstream revenue will double incorrectly, and refund records will vanish from accounting dashboards!"
            prescription["is_safe"] = False
            
        return prescription
        
    except Exception as e:
        print(f"AWS Bedrock Nova Lite error: {e}. Falling back to pre-configured remediation report.")
        if issue_id == "negative_amounts_safe":
            return SAFE_HUMAN_REMEDIATION
        return MOCK_REMEDIATION_REPORT.get(issue_id, {"recommended_fix": "No fix found.", "sql_fix": "-- No fix available"})
