"""
Local Bedrock client wrapper for Data Therapist.
Tries to import from the shared bedrock_helper; falls back to a self-contained implementation.
This avoids sys.path hacks that confuse IDE linters.
"""

import json
import importlib.util
import os


def _load_shared_helper():
    """Attempt to load the shared bedrock_helper module by absolute path."""
    shared_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "shared", "bedrock_helper.py"
    )
    shared_path = os.path.abspath(shared_path)
    if os.path.exists(shared_path):
        spec = importlib.util.spec_from_file_location("bedrock_helper", shared_path)
        mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    return None


_shared = _load_shared_helper()

if _shared:
    # Use the shared helper functions directly
    _call_nova_lite_fn = _shared.call_nova_lite
    _call_nova_pro_fn = _shared.call_nova_pro
    BEDROCK_AVAILABLE = True
else:
    # Self-contained fallback using boto3 directly
    try:
        import boto3

        _bedrock_client = None

        def _get_client():
            global _bedrock_client
            if _bedrock_client is None:
                _bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
            return _bedrock_client

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

        def _call_nova_lite_fn(system: str, user: str, max_tokens: int = 1000) -> str:  # type: ignore[misc]
            return _invoke("amazon.nova-lite-v1:0", system, user, max_tokens, 0.3)

        def _call_nova_pro_fn(system: str, user: str, max_tokens: int = 1500) -> str:  # type: ignore[misc]
            return _invoke("amazon.nova-pro-v1:0", system, user, max_tokens, 0.2)

        BEDROCK_AVAILABLE = True
    except Exception:
        BEDROCK_AVAILABLE = False

        def _call_nova_lite_fn(system: str, user: str, max_tokens: int = 1000) -> str:  # type: ignore[misc]
            raise RuntimeError("Bedrock not available")

        def _call_nova_pro_fn(system: str, user: str, max_tokens: int = 1500) -> str:  # type: ignore[misc]
            raise RuntimeError("Bedrock not available")


def call_nova_lite(system: str, user: str, max_tokens: int = 1000) -> str:
    """Call Amazon Nova Lite via Bedrock."""
    return _call_nova_lite_fn(system, user, max_tokens)


def call_nova_pro(system: str, user: str, max_tokens: int = 1500) -> str:
    """Call Amazon Nova Pro via Bedrock."""
    return _call_nova_pro_fn(system, user, max_tokens)
