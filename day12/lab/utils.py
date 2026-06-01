"""
Shared utilities for all Sigma Intelligence Platform agents.
  - Bedrock caller with retry + exponential backoff
  - Structured logger
  - GE suite versioning (S3-backed)
"""

import boto3, gzip, json, logging, os, time
from datetime import datetime

# ── Logger ────────────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(name)s] %(levelname)s — %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

# ── Bedrock with retry ────────────────────────────────────────────────────────
def call_bedrock(prompt: str,
                 region: str = "us-east-1",
                 model_id: str = "amazon.nova-pro-v1:0",
                 max_tokens: int = 1500,
                 max_attempts: int = 3) -> str:
    """
    Call Bedrock Nova with exponential backoff retry.
    Production fix: never let one Bedrock timeout crash the agent.
    """
    logger = get_logger("bedrock")
    client = boto3.client("bedrock-runtime", region_name=region)
    body   = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.1},
    }

    for attempt in range(1, max_attempts + 1):
        try:
            resp = client.invoke_model(modelId=model_id, body=json.dumps(body))
            return json.loads(resp["body"].read())["output"]["message"]["content"][0]["text"].strip()
        except Exception as e:
            if attempt == max_attempts:
                logger.error(f"Bedrock failed after {max_attempts} attempts: {e}")
                raise
            wait = 2 ** (attempt - 1)   # 1s, 2s, 4s
            logger.warning(f"Bedrock attempt {attempt} failed ({e}). Retrying in {wait}s...")
            time.sleep(wait)

def call_bedrock_lite(prompt: str, region: str = "us-east-1", max_tokens: int = 800) -> str:
    """Nova Lite for fast, cheap routing decisions."""
    return call_bedrock(prompt, region, "amazon.nova-lite-v1:0", max_tokens)

# ── S3 helpers ────────────────────────────────────────────────────────────────
def get_latest_s3_file(bucket: str, prefix: str, region: str = "us-east-1") -> str | None:
    s3      = boto3.client("s3", region_name=region)
    resp    = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        return None
    return sorted(objects, key=lambda x: x["LastModified"], reverse=True)[0]["Key"]

def read_s3_json_gz(bucket: str, key: str, region: str = "us-east-1") -> list[dict]:
    """Read a gzipped NDJSON file from S3 — returns list of dicts."""
    s3   = boto3.client("s3", region_name=region)
    obj  = s3.get_object(Bucket=bucket, Key=key)
    data = gzip.decompress(obj["Body"].read()).decode("utf-8")
    return [json.loads(line) for line in data.strip().splitlines() if line.strip()]

# ── GE Suite versioning ───────────────────────────────────────────────────────
GE_SUITE_PREFIX = "config/ge_suites/"

def load_ge_suite(bucket: str, suite_name: str, region: str = "us-east-1") -> dict | None:
    """
    Load a versioned GE suite from S3.
    Production fix: generate once, version in S3, reuse — don't regenerate every run.
    Returns None if no suite exists yet (first run).
    """
    s3  = boto3.client("s3", region_name=region)
    key = f"{GE_SUITE_PREFIX}{suite_name}.json"
    try:
        obj  = s3.get_object(Bucket=bucket, Key=key)
        suite = json.loads(obj["Body"].read())
        get_logger("ge_versioning").info(f"Loaded existing GE suite: s3://{bucket}/{key}")
        return suite
    except s3.exceptions.NoSuchKey:
        return None
    except Exception:
        return None

def save_ge_suite(bucket: str, suite_name: str, suite: dict, region: str = "us-east-1"):
    """Save a GE suite to S3 for reuse on future runs."""
    s3  = boto3.client("s3", region_name=region)
    key = f"{GE_SUITE_PREFIX}{suite_name}.json"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(suite, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    get_logger("ge_versioning").info(f"GE suite saved: s3://{bucket}/{key}")

# ── Parse JSON from LLM response ─────────────────────────────────────────────
def parse_json_response(response: str) -> dict:
    """Safely extract JSON from LLM response (handles markdown code blocks)."""
    try:
        # Strip markdown code blocks if present
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        start = text.index("{")
        end   = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {}
