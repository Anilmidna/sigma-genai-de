"""
Shared Bedrock helper — Day 9 Case Study
Use call_nova_lite() for fast/cheap calls, call_nova_pro() for deeper reasoning.
"""

import boto3
import json

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name="us-east-1")
    return _client


def _invoke(model_id: str, system: str, user: str, max_tokens: int = 1500, temperature: float = 0.3) -> str:
    body = {
        "messages": [{"role": "user", "content": [{"text": user}]}],
        "system": [{"text": system}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": temperature},
    }
    response = _get_client().invoke_model(
        modelId=model_id,
        body=json.dumps(body),
    )
    result = json.loads(response["body"].read())
    return result["output"]["message"]["content"][0]["text"]


def call_nova_lite(system: str, user: str, max_tokens: int = 1000) -> str:
    return _invoke("amazon.nova-lite-v1:0", system, user, max_tokens, temperature=0.3)


def call_nova_pro(system: str, user: str, max_tokens: int = 1500) -> str:
    return _invoke("amazon.nova-pro-v1:0", system, user, max_tokens, temperature=0.2)
