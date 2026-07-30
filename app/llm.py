"""Single wrapper for structured model calls.

Every call here takes a Pydantic schema, asks the model for JSON, validates
the response against that schema, and retries once — re-deriving the request
from the original text plus the model's own bad output and the validator's
complaint, not repeating the identical request — on a parse failure. This is
the one place that talks to an LLM, per SPEC.md's app/llm.py role.

Key resolution: the workspace's own `gemini` key (BYO-key) first, then the
free-tier GEMINI_API_KEY environment variable, so demo mode still works with
zero pasted keys. If neither is available, generate_structured returns None
and the caller falls back to a non-model path.
"""

import json
import os
import re
from enum import Enum

import httpx
from pydantic import BaseModel, ValidationError

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


class LLMErrorKind(str, Enum):
    INVALID_KEY = "invalid_key"
    ERROR = "error"


class LLMError(RuntimeError):
    """Raised for every generate_structured failure except "no key configured"."""

    def __init__(self, kind: LLMErrorKind, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def _resolve_key(settings: dict[str, str]) -> str | None:
    return settings.get("gemini") or os.environ.get("GEMINI_API_KEY")


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model output")
    return json.loads(match.group(0))


def _safe_gemini_reason(response: httpx.Response) -> str:
    """A sanitized, UI/audit-safe error string — never the key, url, or headers."""
    try:
        message = response.json()["error"]["message"]
        return str(message)[:300]
    except (KeyError, TypeError, ValueError):
        return f"Gemini returned HTTP {response.status_code}"


def _to_llm_error(exc: httpx.HTTPStatusError) -> LLMError:
    response = exc.response
    reason = _safe_gemini_reason(response)

    if response.status_code == 403:
        return LLMError(LLMErrorKind.INVALID_KEY, reason)

    if response.status_code == 400:
        try:
            body = response.json()
            status = body.get("error", {}).get("status")
            message = body.get("error", {}).get("message", "")
        except ValueError:
            status, message = None, ""
        if status == "INVALID_ARGUMENT" and "api key" in message.lower():
            return LLMError(LLMErrorKind.INVALID_KEY, reason)

    return LLMError(LLMErrorKind.ERROR, reason)


def _call_gemini(api_key: str, system: str, user: str) -> str:
    try:
        response = httpx.post(
            GEMINI_URL,
            params={"key": api_key},
            json={
                "system_instruction": {"parts": [{"text": system}]},
                "contents": [{"parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            },
            timeout=30,
        )
    except httpx.RequestError as exc:
        raise LLMError(LLMErrorKind.ERROR, f"could not reach Gemini: {exc}") from exc

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _to_llm_error(exc) from exc

    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_structured(
    schema: type[BaseModel],
    system: str,
    user: str,
    settings: dict[str, str],
) -> BaseModel | None:
    """Ask the model for JSON matching `schema`, validated with one retry.

    Returns None if no LLM key is available anywhere (workspace or free
    tier) — the caller is expected to have a non-model fallback for demo
    mode, per CLAUDE.md's demo-mode non-negotiable. Raises LLMError for
    every other failure mode (credential rejection, network error, or an
    exhausted validation retry), so the caller can distinguish a bad key
    from everything else.
    """
    api_key = _resolve_key(settings)
    if api_key is None:
        return None

    schema_block = json.dumps(schema.model_json_schema())
    first_user = f"{user}\n\nRespond with JSON matching this schema:\n{schema_block}"

    text = _call_gemini(api_key, system, first_user)
    try:
        return schema.model_validate(_extract_json(text))
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as first_error:
        retry_user = (
            f"{first_user}\n\nYour previous response was:\n{text}\n\n"
            f"Your previous response failed validation: {first_error}. "
            "Return only JSON matching the schema above."
        )
        text2 = _call_gemini(api_key, system, retry_user)
        try:
            return schema.model_validate(_extract_json(text2))
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as second_error:
            raise LLMError(
                LLMErrorKind.ERROR,
                f"model output failed validation twice: {second_error}",
            ) from second_error
