import boto3
import json
import os
import re
from datetime import datetime, timezone

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-agent-runtime', region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))

def lambda_handler(event, context):
    """
    Triggered by S3 ObjectCreated event.
    Downloads the transaction file, attempts to load it into Snowflake,
    and invokes the Bedrock Supervisor Agent if loading fails or loads 0 rows.
    """
    print("Received S3 Event:", json.dumps(event))
    
    # 1. Parse bucket and key from S3 event
    try:
        s3_record = event['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = s3_record['object']['key']
    except (KeyError, IndexError) as e:
        print(f"Error parsing S3 event: {e}")
        return {'statusCode': 400, 'body': 'Invalid S3 event format.'}
        
    print(f"Processing file: s3://{bucket_name}/{object_key}")
    
    # Only process files in the bronze/ folder
    if not object_key.startswith('bronze/'):
        print("File is not in bronze/ folder. Skipping Ingestion.")
        return {'statusCode': 200, 'body': 'Skipped non-bronze file.'}
        
    # 2. Download and parse the JSON lines file from S3
    try:
        response = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        records = []
        for line in content.split('\n'):
            if line.strip():
                records.append(json.loads(line))
    except Exception as e:
        print(f"Error reading S3 object: {e}")
        return {'statusCode': 500, 'body': f"Error reading S3: {e}"}
        
    if not records:
        print("S3 file is empty. Skipping Ingestion.")
        return {'statusCode': 200, 'body': 'S3 file is empty.'}

    # 3. Load to Snowflake strictly (without any field remapping/fallback)
    load_result = load_strictly(records)
    print("Snowflake load result:", json.dumps(load_result))
    
    # 4. Check for anomalies (0 rows loaded despite records existing, or error)
    rows_loaded = load_result.get('rows_loaded', 0)
    error = load_result.get('error')
    
    if rows_loaded == 0 or error:
        print("ANOMALY DETECTED: 0 rows loaded to Snowflake or DB error. Triggering Bedrock Agent.")
        incident_msg = (
            f"Dashboard gap detected: 0 transactions loaded from new S3 file s3://{bucket_name}/{object_key}. "
            f"File contains {len(records)} records, but Snowflake row count loaded is 0. "
            f"The pipeline trigger Lambda failed with database error: {error or 'Schema mismatch/date format mismatch'}. "
            f"Investigate the root cause, roll back any bad producer Lambda, replay the missing records from S3, "
            f"create CloudWatch alarms to harden the pipeline, and write an incident report."
        )
        trigger_agent_result = invoke_supervisor(incident_msg, bucket_name)
        return {
            'statusCode': 207,
            'body': {
                'load_result': load_result,
                'agent_trigger': trigger_agent_result
            }
        }
        
    return {
        'statusCode': 200,
        'body': {
            'status': 'SUCCESS',
            'load_result': load_result
        }
    }

def load_strictly(records: list) -> dict:
    """
    Strict loader that mimics the production pipeline.
    It does not contain fallback fields like merchant_nm -> merchant_name
    or date reformatting. It will fail or insert nulls for malformed v2 records.
    """
    try:
        import snowflake.connector
    except ImportError:
        return {"error": "snowflake-connector-python not bundled"}

    ts = datetime.now(timezone.utc).isoformat()
    table_name = f"{os.getenv('SNOWFLAKE_DATABASE','SIGMA')}.{os.getenv('SNOWFLAKE_SCHEMA','SILVER')}.TRANSACTIONS"
    
    try:
        conn = snowflake.connector.connect(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            database=os.getenv("SNOWFLAKE_DATABASE", "SIGMA"),
            schema=os.getenv("SNOWFLAKE_SCHEMA", "SILVER"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "SIGMA_WH"),
        )
        cur = conn.cursor()
        
        # Create temp table
        cur.execute("""
            CREATE TEMPORARY TABLE IF NOT EXISTS temp_strict_transactions (
                transaction_id   VARCHAR,
                merchant_name    VARCHAR,
                category         VARCHAR,
                amount           FLOAT,
                currency         VARCHAR,
                transaction_date DATE,
                status           VARCHAR,
                customer_id      VARCHAR,
                payment_method   VARCHAR,
                merchant_city    VARCHAR,
                _loaded_at       TIMESTAMP_TZ
            )
        """)
        
        # Batch insert raw data strictly (no fallbacks)
        batch_values = []
        for rec in records:
            batch_values.append((
                rec.get("transaction_id", ""),
                rec.get("merchant_name", ""), # Strictly merchant_name (None if using v2)
                rec.get("category", ""),
                float(rec.get("amount", 0) or 0),
                rec.get("currency", "INR"),
                rec.get("transaction_date", ""), # Strictly YYYY-MM-DD
                rec.get("status", ""),
                rec.get("customer_id", ""),
                rec.get("payment_method", ""),
                rec.get("merchant_city", ""),
                ts,
            ))
            
        cur.executemany(
            """INSERT INTO temp_strict_transactions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            batch_values,
        )
        
        # MERGE into target
        cur.execute(f"""
            MERGE INTO {table_name} AS target
            USING temp_strict_transactions AS src
            ON target.transaction_id = src.transaction_id
            WHEN NOT MATCHED THEN INSERT (
                transaction_id, merchant_name, category, amount, currency,
                transaction_date, status, customer_id, payment_method,
                merchant_city, _loaded_at
            ) VALUES (
                src.transaction_id, src.merchant_name, src.category, src.amount,
                src.currency, src.transaction_date, src.status, src.customer_id,
                src.payment_method, src.merchant_city, src._loaded_at
            )
        """)
        
        # Check counts
        cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE _loaded_at = '{ts}'")
        rows_loaded = cur.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        return {
            "status": "LOADED",
            "rows_attempted": len(records),
            "rows_loaded": rows_loaded,
            "loaded_at": ts
        }
        
    except Exception as e:
        return {"status": "FAILED", "rows_loaded": 0, "error": str(e)}

def invoke_supervisor(message: str, bucket_name: str) -> dict:
    """Invokes the Bedrock Supervisor Agent to kick off self-healing."""
    supervisor_id = os.getenv("SUPERVISOR_AGENT_ID")
    alias_id = os.getenv("SUPERVISOR_ALIAS_ID", "TSTALIASID")
    
    if not supervisor_id:
        print("Error: SUPERVISOR_AGENT_ID environment variable not set. Cannot trigger self-healing.")
        return {"status": "SKIPPED", "reason": "SUPERVISOR_AGENT_ID not set"}
        
    session_id = f"sigma-auto-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    
    try:
        response = bedrock.invoke_agent(
            agentId=supervisor_id,
            agentAliasId=alias_id,
            sessionId=session_id,
            inputText=message,
        )
        
        # Read completion to ensure agent runs
        for event in response["completion"]:
            if "chunk" in event:
                text = event["chunk"]["bytes"].decode("utf-8")
                print(f"Agent stream: {text}", end="")
                
        return {"status": "SUCCESS", "session_id": session_id}
    except Exception as e:
        print(f"Error invoking Bedrock agent: {e}")
        return {"status": "FAILED", "error": str(e)}
