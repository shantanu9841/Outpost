"""Single wrapper for structured model calls.

Every call here takes a Pydantic schema, asks the model for JSON, validates
the response against that schema, and retries once — re-deriving the request
from the original text plus the model's own bad output and the validator's
complaint, not repeating the identical request — on a parse failure. This is
the one place that talks to an LLM, per SPEC.md's app/llm.py role.

Two layers of structure enforcement, not one: (1) the request asks Gemini to
enforce the schema server-side via generationConfig.responseJsonSchema, and
(2) the response is still validated locally against the same Pydantic schema
with a corrective second attempt. Provider-side enforcement complements local
validation; it does not replace it.

No provider response — success or failure — is ever allowed to raise a raw
JSONDecodeError/KeyError/IndexError/TypeError past this module. Every failure
becomes an LLMError carrying a sanitized message that never contains the API
key, request headers, the credential-bearing URL, or a raw provider payload.

Key resolution: the workspace's own `gemini` key (BYO-key) first, then the
GEMINI_API_KEY environment variable. If neither is available,
generate_structured returns None and the caller falls back to a non-model
path (demo-mode non-negotiable).
"""

import json
import os
import re
from enum import Enum

import httpx
from pydantic import BaseModel, ValidationError

GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# JSON Schema keywords Pydantic emits that Gemini's structured-output schema
# validator does not need and can reject. Stripped recursively before the
# schema is sent. Kept as a named set so it is easy to extend if the provider
# rejects another keyword.
_UNSUPPORTED_SCHEMA_KEYS = {"default", "$schema"}


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


def _response_schema(schema: type[BaseModel]) -> dict:
    """Derive Gemini's responseJsonSchema from a Pydantic schema.

    Uses the standard JSON Schema that Pydantic produces, minus a few keywords
    Gemini's structured-output validator does not accept.
    """
    return _strip_unsupported(schema.model_json_schema())


def _strip_unsupported(node):
    if isinstance(node, dict):
        return {
            key: _strip_unsupported(value)
            for key, value in node.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYS
        }
    if isinstance(node, list):
        return [_strip_unsupported(item) for item in node]
    return node


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response, tolerating code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model output")
    return json.loads(match.group(0))


def _safe_gemini_reason(response: httpx.Response, api_key: str) -> str:
    """A sanitized, UI/audit-safe error string — never the key, url, or headers."""
    try:
        message = response.json()["error"]["message"]
    except (KeyError, TypeError, ValueError, IndexError):
        return f"Gemini returned HTTP {response.status_code}"
    if isinstance(message, str) and message.strip():
        return message.replace(api_key, "[REDACTED]")[:300]
    return f"Gemini returned HTTP {response.status_code}"


def _to_llm_error(exc: httpx.HTTPStatusError, api_key: str) -> LLMError:
    response = exc.response
    reason = _safe_gemini_reason(response, api_key)

    if response.status_code == 403:
        return LLMError(LLMErrorKind.INVALID_KEY, reason)

    if response.status_code == 400:
        try:
            body = response.json()
            status = body.get("error", {}).get("status")
            message = body.get("error", {}).get("message", "")
        except (ValueError, AttributeError, TypeError):
            status, message = None, ""
        if status == "INVALID_ARGUMENT" and "api key" in str(message).lower():
            return LLMError(LLMErrorKind.INVALID_KEY, reason)

    return LLMError(LLMErrorKind.ERROR, reason)


def _extract_text(data: object) -> str:
    """Safely pull the model's text out of a 200 response body.

    Any missing/empty/misshaped part of the expected candidates→content→parts
    path becomes an LLMError(ERROR), never a raw KeyError/IndexError/TypeError.
    """
    if not isinstance(data, dict):
        raise LLMError(LLMErrorKind.ERROR, "Gemini returned an unexpected response shape")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise LLMError(LLMErrorKind.ERROR, "Gemini returned no candidates")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        raise LLMError(LLMErrorKind.ERROR, "Gemini response was missing content parts")
    texts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not texts:
        raise LLMError(LLMErrorKind.ERROR, "Gemini response contained no text")
    return "".join(texts)


def _call_gemini(api_key: str, system: str, user: str, response_schema: dict) -> str:
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": response_schema,
        },
    }
    try:
        response = httpx.post(GEMINI_URL, params={"key": api_key}, json=body, timeout=30)
    except httpx.RequestError as exc:
        # str(exc) can include the request URL, which carries the API key as a
        # query param — never interpolate it. The exception type is enough.
        raise LLMError(
            LLMErrorKind.ERROR, f"could not reach Gemini ({type(exc).__name__})"
        ) from exc

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _to_llm_error(exc, api_key) from exc

    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMError(LLMErrorKind.ERROR, "Gemini returned a non-JSON response") from exc

    return _extract_text(data)


def generate_structured(
    schema: type[BaseModel],
    system: str,
    user: str,
    settings: dict[str, str],
) -> BaseModel | None:
    """Ask the model for JSON matching `schema`, validated with one retry.

    Returns None if no LLM key is available anywhere (workspace or env) — the
    caller is expected to have a non-model fallback for demo mode, per
    CLAUDE.md's demo-mode non-negotiable. Raises LLMError for every other
    failure mode (credential rejection, transport/provider failure, malformed
    provider response, or an exhausted validation retry), so the caller can
    distinguish a bad key from everything else and never sees a raw exception.
    """
    api_key = _resolve_key(settings)
    if api_key is None:
        return None

    response_schema = _response_schema(schema)
    schema_block = json.dumps(response_schema)
    first_user = f"{user}\n\nRespond with JSON matching this schema:\n{schema_block}"

    text = _call_gemini(api_key, system, first_user, response_schema)
    try:
        return schema.model_validate(_extract_json(text))
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as first_error:
        retry_user = (
            f"{first_user}\n\nYour previous response was:\n{text}\n\n"
            f"Your previous response failed validation: {first_error}. "
            "Return only JSON matching the schema above."
        )
        text2 = _call_gemini(api_key, system, retry_user, response_schema)
        try:
            return schema.model_validate(_extract_json(text2))
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as second_error:
            raise LLMError(
                LLMErrorKind.ERROR,
                f"model output failed validation twice: {second_error}",
            ) from second_error
