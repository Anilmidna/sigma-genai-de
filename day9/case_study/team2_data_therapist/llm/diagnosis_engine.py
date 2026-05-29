"""
AI Diagnosis Engine using AWS Bedrock Nova Pro.
Scans raw transactions and generates a structured, enterprise-grade data quality report.
Includes robust mock fallback for offline and local demo modes.
"""

import json
import boto3
import pandas as pd
import numpy as np

# Mock diagnosis data that perfectly aligns with our synthetic data generator.
# This represents what Nova Pro would output when presented with our injected errors.
MOCK_DIAGNOSIS_REPORT = [
    {
        "id": "duplicates",
        "title": "Duplicate Transaction IDs",
        "severity": "HIGH",
        "affected_rows": "~16 rows (8 pairs)",
        "confidence": "95%",
        "description": "Multiple transactions share identical transaction_id values. Some are exact duplicates, while others represent the same transaction ID with slight variations in amount, timestamp, or source system.",
        "root_cause": "Kafka message replay retries, or ingestion pipeline failure causing dual-publishing from Source System B.",
        "business_impact": "Double counting of transactions, incorrect downstream revenue aggregation, and primary key violations in the Silver layer."
    },
    {
        "id": "null_ids",
        "title": "Null Transaction IDs",
        "severity": "HIGH",
        "affected_rows": "3 rows",
        "confidence": "98%",
        "description": "Records are ingested with missing or null transaction_id values, leaving them without a unique identifier.",
        "root_cause": "Upstream schema failure or incomplete database serialization at the point of source collection.",
        "business_impact": "Inability to index, join, or trace these records downstream. Severe risk of orphaned records."
    },
    {
        "id": "null_merchants",
        "title": "Missing Merchant Names",
        "severity": "MEDIUM",
        "affected_rows": "4 rows",
        "confidence": "89%",
        "description": "Transactions are ingested with null merchant_name values.",
        "root_cause": "Ingestion filter malfunction or missing merchant metadata mapping in Source System C.",
        "business_impact": "Incomplete merchant performance dashboards and skewed category-level aggregations in Gold reports."
    },
    {
        "id": "null_customers",
        "title": "Missing Customer IDs",
        "severity": "MEDIUM",
        "affected_rows": "5 rows",
        "confidence": "91%",
        "description": "Transactions are missing the customer_id identifier.",
        "root_cause": "Guest checkouts or missing session states during mobile app checkouts.",
        "business_impact": "Breaks customer segmentation, loyalty calculations, and customer lifetime value (CLV) aggregates."
    },
    {
        "id": "malformed_timestamps",
        "title": "Malformed Timestamps",
        "severity": "HIGH",
        "affected_rows": "5 rows",
        "confidence": "94%",
        "description": "Timestamps are written in non-standard formats (e.g. DD-MM-YYYY or YYYY/MM/DD HH:MM instead of YYYY-MM-DD HH:MM:SS).",
        "root_cause": "System localization differences; Source System A formatting dates based on regional settings instead of using ISO-8601.",
        "business_impact": "Silent parsing failures during ETL processes, resulting in null values or incorrect chronological sorting."
    },
    {
        "id": "future_timestamps",
        "title": "Impossible Future Timestamps",
        "severity": "HIGH",
        "affected_rows": "3 rows",
        "confidence": "97%",
        "description": "Transactions with timestamp values set in the distant future (e.g. 2099-12-31).",
        "root_cause": "Default system placeholder timestamps or incorrect epoch conversion on device-level local clocks.",
        "business_impact": "Distorts time-series forecasts and invalidates daily and weekly operational dashboard summaries."
    },
    {
        "id": "merchant_spellings",
        "title": "Inconsistent Merchant Spellings",
        "severity": "MEDIUM",
        "affected_rows": "~30 rows",
        "confidence": "85%",
        "description": "Varying representations of the same corporate merchant (e.g., 'Amazon', 'AMAZON', 'amazon', 'Amazon Inc', 'Amazon.com ').",
        "root_cause": "Free-form text input at customer point of sale, combined with a lack of merchant standardization lookup tables.",
        "business_impact": "Dilutes merchant analytics. Shows separate metrics for 'Amazon' and 'AMAZON', breaking merchant ranking reports."
    },
    {
        "id": "negative_amounts",
        "title": "Negative Transaction Amounts",
        "severity": "HIGH",
        "affected_rows": "~30-40 rows",
        "confidence": "92%",
        "description": "Transaction amounts are negative values (e.g. -$120.00).",
        "root_cause": "Refunds and chargeback events logged directly in the transaction ledger as negative adjustments rather than positive reversals.",
        "business_impact": "Naive downstream queries will calculate double purchases if not isolated, or incorrectly reduce standard revenue metrics."
    },
    {
        "id": "outliers",
        "title": "Extreme Outlier Amounts",
        "severity": "MEDIUM",
        "affected_rows": "2 rows",
        "confidence": "90%",
        "description": "Transaction amounts that are incredibly large (e.g. +/- $5,000,000.00).",
        "root_cause": "Ingestion schema error or fat-finger numeric entry at checkout.",
        "business_impact": "Skews average ticket size and distorts financial dashboards, showing artificial spikes in revenue."
    }
]

def generate_profile_summary(df):
    """Generates a text summary of the dataset anomalies to feed into the LLM context."""
    summary = []
    summary.append(f"Dataset Size: {len(df)} rows")
    summary.append(f"Columns: {list(df.columns)}")
    
    # Missing counts
    nulls = df.isnull().sum()
    summary.append(f"Missing Values:")
    for col, val in nulls.items():
        if val > 0:
            summary.append(f"  - {col}: {val} missing values")
            
    # Duplicate transaction ID count
    if 'transaction_id' in df.columns:
        valid_ids = df['transaction_id'].dropna()
        dups = len(valid_ids) - len(valid_ids.unique())
        summary.append(f"Duplicate Transaction IDs: {dups} occurrences")
        
    # Transaction Amount summary
    if 'transaction_amount' in df.columns:
        neg_count = (df['transaction_amount'] < 0).sum()
        max_val = df['transaction_amount'].max()
        min_val = df['transaction_amount'].min()
        summary.append(f"Transaction Amounts:")
        summary.append(f"  - Negative Amounts: {neg_count} occurrences")
        summary.append(f"  - Minimum Value: {min_val}")
        summary.append(f"  - Maximum Value: {max_val}")
        
    # Merchant Name variations
    if 'merchant_name' in df.columns:
        merchants = df['merchant_name'].dropna().unique()
        amazon_like = [m for m in merchants if 'amazon' in m.lower()]
        swiggy_like = [m for m in merchants if 'swiggy' in m.lower()]
        summary.append(f"Merchant Variations:")
        summary.append(f"  - Amazon-like spellings: {amazon_like}")
        summary.append(f"  - Swiggy-like spellings: {swiggy_like}")
        
    # Timestamp issues
    if 'transaction_timestamp' in df.columns:
        future_dates = df[df['transaction_timestamp'].astype(str).str.startswith('2099')].shape[0]
        slashes = df[df['transaction_timestamp'].astype(str).str.contains('/')].shape[0]
        dashes_d = df[df['transaction_timestamp'].astype(str).str.contains('-') & (df['transaction_timestamp'].astype(str).str.len() == 10)].shape[0]
        summary.append(f"Timestamp formats:")
        summary.append(f"  - Future dates (2099): {future_dates}")
        summary.append(f"  - Slash format (YYYY/MM/DD): {slashes}")
        summary.append(f"  - Short dash format (DD-MM-YYYY): {dashes_d}")

    # Add a sample of first 15 rows for LLM inspection
    sample_json = df.head(15).to_json(orient='records')
    
    return "\n".join(summary), sample_json

def diagnose_dataset(df, use_bedrock=False):
    """
    Diagnoses data quality issues in the DataFrame.
    By default, returns the high-fidelity mock report to ensure reliability and speed.
    If use_bedrock=True, attempts to query AWS Bedrock Nova Pro.
    """
    if not use_bedrock:
        return MOCK_DIAGNOSIS_REPORT
        
    # Perform Bedrock Call
    try:
        profile_text, sample_json = generate_profile_summary(df)
        
        system_prompt = (
            "You are a Senior Data Quality Engineer and an expert 'AI Data Therapist' at Sigma DataTech. "
            "Your task is to analyze the data profile summary and sample records of our raw Bronze table and output "
            "a structured JSON list of data quality issues. Do not output conversational text or explanation outside the JSON. "
            "Each issue in the list must be a JSON object with the following fields EXACTLY:\n"
            "- id: a unique identifier for the issue (e.g. 'duplicates', 'null_merchants', 'negative_amounts', 'null_customers', 'malformed_timestamps', 'future_timestamps', 'merchant_spellings', 'outliers', 'null_ids')\n"
            "- title: clear issue name\n"
            "- severity: 'HIGH', 'MEDIUM', or 'LOW'\n"
            "- affected_rows: text describing row count/percentage (e.g. '3 rows' or '~15 rows')\n"
            "- confidence: confidence percentage string (e.g. '95%')\n"
            "- description: detailed technical explanation of the issue\n"
            "- root_cause: logical hypothesis of what upstream system, pipeline, or Kafka queue failure caused this\n"
            "- business_impact: detailed description of what business logic, downstream systems, or metrics this issue breaks\n"
        )
        
        user_message = (
            f"Here is the data profile summary of our raw Bronze transaction table:\n\n"
            f"{profile_text}\n\n"
            f"Here is a sample of some raw rows:\n"
            f"{sample_json}\n\n"
            f"Please diagnose all data quality issues. Ensure the response is a valid JSON list of objects containing all 8 fields for each issue."
        )
        
        # Invoke Nova Pro
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        body = {
            "messages": [{"role": "user", "content": [{"text": user_message}]}],
            "system": [{"text": system_prompt}],
            "inferenceConfig": {"maxTokens": 2000, "temperature": 0.2},
        }
        
        response = client.invoke_model(
            modelId="amazon.nova-pro-v1:0",
            body=json.dumps(body),
        )
        
        result_text = json.loads(response["body"].read())["output"]["message"]["content"][0]["text"]
        
        # Clean up Markdown blocks if the LLM wrapped it in ```json ... ```
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        diagnoses = json.loads(result_text.strip())
        return diagnoses
        
    except Exception as e:
        print(f"AWS Bedrock Nova Pro error: {e}. Falling back to pre-configured high-fidelity diagnosis report.")
        return MOCK_DIAGNOSIS_REPORT

if __name__ == "__main__":
    from synthetic_data_generator import generate_dirty_data
    df = generate_dirty_data()
    report = diagnose_dataset(df, use_bedrock=False)
    print(f"Report generated with {len(report)} findings.")
    print(json.dumps(report[0], indent=2))
