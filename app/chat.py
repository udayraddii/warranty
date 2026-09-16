import os
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv(override=True)

GENAI_ENABLED = os.getenv("GENAI_ENABLED", "false").lower() == "true"
GENAI_AUTH_URL = os.getenv("GENAI_AUTH_URL", "")
GENAI_CLIENT_ID = os.getenv("GENAI_CLIENT_ID", "")
GENAI_CLIENT_SECRET = os.getenv("GENAI_CLIENT_SECRET", "")
GENAI_RESOURCE_GROUP = os.getenv("GENAI_RESOURCE_GROUP", "")
GENAI_DEPLOYMENT_URL = os.getenv("GENAI_DEPLOYMENT_URL", "")
GENAI_MODEL = os.getenv("GENAI_MODEL", "default-model")
GENAI_VERIFY_SSL = os.getenv("GENAI_VERIFY_SSL", "true").lower() == "true"
GENAI_TIMEOUT_SECONDS = int(os.getenv("GENAI_TIMEOUT_SECONDS", "60"))
GENAI_API_VERSION = os.getenv("GENAI_API_VERSION", "")


def _get_access_token() -> str:
    if not GENAI_AUTH_URL or not GENAI_CLIENT_ID or not GENAI_CLIENT_SECRET:
        raise ValueError("Missing GENAI auth configuration")

    token_response = requests.post(
        GENAI_AUTH_URL,
        data={"grant_type": "client_credentials"},
        auth=(GENAI_CLIENT_ID, GENAI_CLIENT_SECRET),
        timeout=GENAI_TIMEOUT_SECONDS,
        verify=GENAI_VERIFY_SSL,
    )
    token_response.raise_for_status()
    token_json = token_response.json()

    access_token = token_json.get("access_token")
    if not access_token:
        raise ValueError(f"No access_token returned from auth service: {token_json}")

    return access_token


def _build_headers(access_token: str) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if GENAI_RESOURCE_GROUP:
        headers["AI-Resource-Group"] = GENAI_RESOURCE_GROUP
    return headers


def _extract_text(response_json: Dict[str, Any]) -> str:
    """
    Tries common SAP AI Core / AI Launchpad compatible response shapes.
    Falls back to stringifying the payload if needed.
    """
    if "choices" in response_json and response_json["choices"]:
        message = response_json["choices"][0].get("message", {})
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content

        text = response_json["choices"][0].get("text")
        if isinstance(text, str):
            return text

    if "content" in response_json and isinstance(response_json["content"], str):
        return response_json["content"]

    return str(response_json)


def generate_warranty_explanation(claim_summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Advisory-only LLM explanation.
    Expects SAP AI Hub compatible endpoint and bearer token in env vars.

    Required env vars:
    - GENAI_ENABLED=true
    - GENAI_AUTH_URL
    - GENAI_CLIENT_ID
    - GENAI_CLIENT_SECRET
    - GENAI_DEPLOYMENT_URL

    Optional env vars:
    - GENAI_MODEL
    """
    if not GENAI_ENABLED:
        return {
            "enabled": False,
            "explanation": "GenAI is disabled.",
            "advisory_only": True
        }

    ai_url = GENAI_DEPLOYMENT_URL.rstrip("/")
    if not ai_url.endswith("/v1/chat/completions"):
        ai_url = f"{ai_url}/v1/chat/completions"
    ai_model = GENAI_MODEL

    if not ai_url or not GENAI_AUTH_URL or not GENAI_CLIENT_ID or not GENAI_CLIENT_SECRET:
        return {
            "enabled": False,
            "explanation": "LLM integration is not configured. Ensure GENAI_AUTH_URL, GENAI_CLIENT_ID, GENAI_CLIENT_SECRET and GENAI_DEPLOYMENT_URL are set.",
            "model": ai_model,
            "advisory_only": True,
        }

    system_prompt = (
        "You are an SAP warranty intelligence copilot. "
        "Use only the provided evidence. "
        "Separate observed evidence from inferred causes. "
        "Do not approve claims, do not make financial posting decisions, and keep recommendations advisory."
    )

    user_prompt = f"""
Generate a concise warranty-claim explanation for this deterministic result.

Return sections:
1. Observed evidence
2. Likely pattern interpretation
3. Recommended next actions
4. Compliance note

Claim summary:
{claim_summary}
"""

    payload = {
        "model": ai_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    try:
        access_token = _get_access_token()
        headers = _build_headers(access_token)
        response = requests.post(
            ai_url,
            headers=headers,
            json=payload,
            timeout=GENAI_TIMEOUT_SECONDS,
            verify=GENAI_VERIFY_SSL,
        )
        response.raise_for_status()
        response_json = response.json()

        return {
            "enabled": True,
            "model": ai_model,
            "explanation": _extract_text(response_json),
            "raw_response": response_json,
            "advisory_only": True,
        }
    except requests.HTTPError as exc:
        response = exc.response
        provider_detail = response.text[:500] if response is not None else str(exc)
        return {
            "enabled": False,
            "model": ai_model,
            "explanation": f"LLM request failed ({response.status_code if response is not None else 'HTTP error'}): {provider_detail}",
            "advisory_only": True,
        }
    except Exception as exc:
        return {
            "enabled": False,
            "model": ai_model,
            "explanation": f"LLM request failed: {exc}",
            "advisory_only": True,
        }
