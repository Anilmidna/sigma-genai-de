"""
Day 6 — SQL Brain Lab: LLM call helpers (Bedrock Nova + Ollama fallback).
"""

import json
import time
import boto3
import requests
from dataclasses import dataclass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


def call_bedrock(system: str, user_message: str, model_id: str = "amazon.nova-lite-v1:0",
                 max_tokens: int = 2000) -> tuple:
    """Call AWS Bedrock via the Converse API. Returns (text, Usage) or (None, error_str)."""
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")

        messages = [{"role": "user", "content": [{"text": user_message}]}]
        system_list = [{"text": system}] if system else None

        kwargs = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.3},
        }
        if system_list:
            kwargs["system"] = system_list

        response = client.converse(**kwargs)

        text = response["output"]["message"]["content"][0]["text"]
        usage_data = response.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("inputTokens", 0),
            output_tokens=usage_data.get("outputTokens", 0),
        )
        return text, usage

    except Exception as e:
        return None, str(e)


def call_ollama(system: str, user_message: str, model: str = "qwen2.5:7b",
                max_tokens: int = 2000) -> tuple:
    """Call local Ollama. Returns (text, Usage) or (None, error_str)."""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})

        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": 0.3},
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        text = data["message"]["content"]
        usage = Usage(
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
        )
        return text, usage

    except requests.exceptions.ConnectionError:
        return None, "Cannot connect to Ollama. Is it running? Start with: ollama serve"
    except Exception as e:
        return None, str(e)


def call_llm(system: str, user_message: str, backend: str = "bedrock",
             model: str = None, max_tokens: int = 2000) -> tuple:
    """Unified LLM call. backend = 'bedrock' or 'ollama'."""
    if backend == "ollama":
        model = model or "qwen2.5:7b"
        return call_ollama(system, user_message, model=model, max_tokens=max_tokens)
    else:
        model = model or "amazon.nova-lite-v1:0"
        return call_bedrock(system, user_message, model_id=model, max_tokens=max_tokens)
