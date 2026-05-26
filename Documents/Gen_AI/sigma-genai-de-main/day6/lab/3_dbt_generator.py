"""
dbt Project Generator — Day 6, Module 3
Sigma Intelligence Platform | GenAI for Data Engineering

═══════════════════════════════════════════════════════════════
MISSION:
  Raw SQL in production is tech debt. Sigma DataTech needs every
  query as a versioned, tested, documented dbt model. Manually
  writing dbt YAML is tedious. Your job: AI generates the entire
  dbt project scaffold from a schema description — in 60 seconds.

WHY THIS MATTERS (vs writing dbt manually):
  - Speed → full project scaffold in 1 prompt (vs 2 hours manual)
  - Consistency → AI follows your naming conventions every time
  - Tests included → AI generates schema tests you'd forget to write
  - Still needs YOUR review → AI gets ref()/source() wrong sometimes

WHERE THIS FITS IN THE PLATFORM:
  Today: generate dbt project from schema
  Day 7: AI generates PySpark code that feeds INTO these dbt models
  Day 8: AI generates tests for these dbt models (CI/CD)
  Day 11: Governance agent auto-generates docs for dbt models
═══════════════════════════════════════════════════════════════

HOW TO RUN:
  python 3_dbt_generator.py

GENERATES:
  sigma_dbt/
  ├── models/staging/stg_transactions.sql
  ├── models/staging/schema.yml
  ├── models/marts/mart_merchant_performance.sql
  └── models/marts/schema.yml

"""

import boto3
import os
from sample_data import SCHEMA_COMPACT

# ── CONFIGURATION ──────────────────────────────────────────
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
MODEL_ID = 'amazon.nova-pro-v1:0'


def generate_dbt_file(file_type: str, description: str) -> str:
    """Generate a single dbt file using AI."""
    system = """You are a senior Analytics Engineer specializing in dbt.
Generate production-quality dbt code following these conventions:
- Use CTEs for readability
- Prefix: staging=stg_, intermediate=int_, marts=mart_
- Use Jinja ref() and source() macros correctly
- Include column descriptions in schema.yml
- Add appropriate dbt tests (not_null, unique, accepted_values, relationships)
Return ONLY the file content. No explanation. No markdown fences unless it's YAML/SQL."""

    user = f"""Schema:
{SCHEMA_COMPACT}

Generate this file: {file_type}
Requirements: {description}

Return only the file content."""

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": 2500, "temperature": 0.2},
    )
    return response["output"]["message"]["content"][0]["text"]


def scaffold_dbt_project():
    """Generate a complete dbt project structure."""
    # Create directory structure
    dirs = [
        "sigma_dbt/models/staging",
        "sigma_dbt/models/marts",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    files_to_generate = [
        {
            "path": "sigma_dbt/models/staging/stg_transactions.sql",
            "type": "dbt staging model SQL",
            "desc": "Clean fact_transactions: rename to snake_case, cast types, filter out test data (merchant_id starting with TEST_), add loaded_at timestamp",
        },
        {
            "path": "sigma_dbt/models/staging/schema.yml",
            "type": "dbt schema.yml for staging",
            "desc": "Source definition pointing to sigma_analytics database, column descriptions, tests: not_null on PK, unique on PK, accepted_values on status and payment_method",
        },
        {
            "path": "sigma_dbt/models/marts/mart_merchant_performance.sql",
            "type": "dbt mart model SQL",
            "desc": "Aggregate merchant KPIs: total_revenue (COMPLETED only), total_transactions, failed_count, failure_rate_pct, avg_transaction_value, unique_customers. JOIN dim_merchant for names. Use CTEs.",
        },
        {
            "path": "sigma_dbt/models/marts/schema.yml",
            "type": "dbt schema.yml for marts",
            "desc": "Model docs + tests: not_null on merchant_id, test that failure_rate_pct is between 0 and 100, test that total_revenue >= 0. Include ONE test that SHOULD FAIL if bad data has status='CANCELLED'.",
        },
    ]

    print("Generating dbt project...\n")
    for file_info in files_to_generate:
        print(f"  Generating: {file_info['path']}")
        content = generate_dbt_file(file_info["type"], file_info["desc"])

        # Clean markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            content = content.rsplit("```", 1)[0]

        with open(file_info["path"], "w") as f:
            f.write(content)
        print(f"    Saved ({len(content)} chars)")

    print(f"\n{'=' * 60}")
    print("dbt PROJECT SCAFFOLDED")
    print(f"{'=' * 60}")
    print(f"Output: sigma_dbt/")
    print(f"\nReview checklist:")
    print(f"  [ ] ref() calls point to real model names?")
    print(f"  [ ] source() has correct database.schema?")
    print(f"  [ ] Revenue filters on STATUS='COMPLETED'?")
    print(f"  [ ] Tests include not_null, unique, accepted_values?")
    print(f"  [ ] One test deliberately catches bad data?")


if __name__ == "__main__":
    scaffold_dbt_project()
