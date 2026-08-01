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

Key resolution: strictly the workspace's own `gemini` key (BYO-key). There is
no environment-variable fallback (Slice 6) — every LLM workflow is
workspace-key-only, so a key that happens to be set in the process
environment can never trigger a model call for a workspace that hasn't
pasted its own. If no workspace key is available, generate_structured
returns None and the caller falls back to a non-model path (demo-mode
non-negotiable).

Authentication: the API key is sent only via the `x-goog-api-key` request
header (Slice 6) — never as a URL query parameter — matching Apify's
`Authorization: Bearer` and YouTube's `X-goog-api-key` precedent (Slice 5).
No request URL built by this module is ever credential-bearing.

Usage accounting: every response actually received from Gemini — success or
failure, 2xx or not, well-formed or not — produces exactly one TokenUsage
record via _extract_usage. The only call that produces zero usage records is
one where no HTTP request was ever issued at all (no key configured). See
generate_structured_with_usage's docstring for the full accumulation rule.
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum

import httpx
from pydantic import BaseModel, ValidationError

GEMINI_MODEL = "gemini-3.6-flash"
REQUEST_TIMEOUT_SECS = 30

# JSON Schema keywords Pydantic emits that Gemini's structured-output schema
# validator does not need and can reject. Stripped recursively before the
# schema is sent. Kept as a named set so it is easy to extend if the provider
# rejects another keyword.
_UNSUPPORTED_SCHEMA_KEYS = {"default", "$schema"}


def _url(model: str) -> str:
    """The Gemini generateContent endpoint for a given model. No query
    string — the API key is sent only as a header (module docstring)."""
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMErrorKind(str, Enum):
    INVALID_KEY = "invalid_key"
    ERROR = "error"


@dataclass
class TokenUsage:
    """One issued HTTP attempt's token accounting, best-effort.

    Every field except `model` is `int | None` — `None` means genuinely
    unknown for that attempt (a transport failure, a malformed response, or
    a response whose usageMetadata is missing/malformed), never a silent
    zero. See _extract_usage for the exact population rule per field.
    """

    model: str
    prompt_tokens: int | None
    candidates_tokens: int | None
    thinking_tokens: int | None
    total_tokens: int | None
    thinking_tokens_derived: bool = False


@dataclass
class MeasuredResult:
    """generate_structured_with_usage's return shape: the parsed value (or
    None if no key was configured) plus every attempt's usage, in order."""

    value: BaseModel | None
    usage: list[TokenUsage] = field(default_factory=list)


class LLMError(RuntimeError):
    """Raised for every generate_structured failure except "no key configured"."""

    def __init__(self, kind: LLMErrorKind, message: str, usage: list[TokenUsage] | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.usage = usage if usage is not None else []


def _resolve_key(settings: dict[str, str]) -> str | None:
    return settings.get("gemini")


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


def _nonneg_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _derive_thinking(
    meta: dict, prompt: int | None, candidates: int | None, total: int | None
) -> tuple[int | None, bool]:
    """thinking_tokens plus whether it was derived rather than provider-reported.

    thoughtsTokenCount present -> use it directly (provider-reported).
    Otherwise, only derivable (and only "derived") when prompt/candidates/
    total are all known and total >= prompt + candidates (these tool-free
    structured-output calls never report a total smaller than that sum);
    every other case is unknown, never assumed zero.
    """
    if "thoughtsTokenCount" in meta:
        return _nonneg_int(meta.get("thoughtsTokenCount")), False
    if prompt is not None and candidates is not None and total is not None and total >= prompt + candidates:
        return total - prompt - candidates, True
    return None, False


def _extract_usage(response: httpx.Response, model: str) -> TokenUsage:
    """Never raises. Works identically whether the response was a 200 or an
    error status — an error body is still checked for authoritative
    usageMetadata, in case the provider ever includes it."""
    try:
        body = response.json()
    except (ValueError, TypeError):
        return TokenUsage(model, None, None, None, None)
    if not isinstance(body, dict):
        return TokenUsage(model, None, None, None, None)
    meta = body.get("usageMetadata")
    if not isinstance(meta, dict):
        return TokenUsage(model, None, None, None, None)

    prompt = _nonneg_int(meta.get("promptTokenCount"))
    candidates = _nonneg_int(meta.get("candidatesTokenCount"))
    total = _nonneg_int(meta.get("totalTokenCount"))
    thinking, derived = _derive_thinking(meta, prompt, candidates, total)
    return TokenUsage(model, prompt, candidates, thinking, total, thinking_tokens_derived=derived)


def _to_llm_error(exc: httpx.HTTPStatusError, api_key: str, usage: TokenUsage) -> LLMError:
    response = exc.response
    reason = _safe_gemini_reason(response, api_key)

    if response.status_code == 403:
        return LLMError(LLMErrorKind.INVALID_KEY, reason, usage=[usage])

    if response.status_code == 400:
        try:
            body = response.json()
            status = body.get("error", {}).get("status")
            message = body.get("error", {}).get("message", "")
        except (ValueError, AttributeError, TypeError):
            status, message = None, ""
        if status == "INVALID_ARGUMENT" and "api key" in str(message).lower():
            return LLMError(LLMErrorKind.INVALID_KEY, reason, usage=[usage])

    return LLMError(LLMErrorKind.ERROR, reason, usage=[usage])


def _extract_text(data: object) -> str:
    """Safely pull the model's text out of a 200 response body.

    Any missing/empty/misshaped part of the expected candidates→content→parts
    path becomes an LLMError(ERROR), never a raw KeyError/IndexError/TypeError.
    Raised by the caller, which attaches this attempt's usage.
    """
    if not isinstance(data, dict):
        raise ValueError("Gemini returned an unexpected response shape")
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini returned no candidates")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list) or not parts:
        raise ValueError("Gemini response was missing content parts")
    texts = [
        part["text"]
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    if not texts:
        raise ValueError("Gemini response contained no text")
    return "".join(texts)


def _call_gemini(
    api_key: str, system: str, user: str, response_schema: dict, model: str
) -> tuple[str, TokenUsage]:
    """Issue one Gemini request. Returns (text, usage) on success.

    Never returns a bare exception without usage attached: every raise path
    below carries `usage=[<this attempt's TokenUsage>]` on the LLMError, per
    the module docstring's accounting guarantee. A transport failure (no
    response object at all) is the only case with no response to extract
    from, and still produces a full all-unknown TokenUsage.
    """
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": response_schema,
        },
    }
    try:
        response = httpx.post(
            _url(model),
            headers={"x-goog-api-key": api_key},
            json=body,
            timeout=REQUEST_TIMEOUT_SECS,
        )
    except httpx.RequestError as exc:
        # str(exc) can include request details — never interpolate it. The
        # exception type is enough. No response was received, so usage is
        # fully unknown, not omitted.
        raise LLMError(
            LLMErrorKind.ERROR,
            f"could not reach Gemini ({type(exc).__name__})",
            usage=[TokenUsage(model, None, None, None, None)],
        ) from exc

    # Extracted once, on the raw response, before any status-code check —
    # the same best-effort path serves both success and every failure mode.
    usage = _extract_usage(response, model)

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _to_llm_error(exc, api_key, usage) from exc

    try:
        data = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise LLMError(
            LLMErrorKind.ERROR, "Gemini returned a non-JSON response", usage=[usage]
        ) from exc

    try:
        text = _extract_text(data)
    except ValueError as exc:
        raise LLMError(LLMErrorKind.ERROR, str(exc), usage=[usage]) from exc

    return text, usage


def generate_structured_with_usage(
    schema: type[BaseModel],
    system: str,
    user: str,
    settings: dict[str, str],
    *,
    model: str = GEMINI_MODEL,
) -> MeasuredResult:
    """Ask the model for JSON matching `schema`, validated with one retry,
    with every issued attempt's token usage collected in order.

    Returns MeasuredResult(None, []) if no workspace `gemini` key is
    configured — the only case with zero usage entries, since no request was
    ever issued. The caller falls back to a non-model path (demo-mode
    non-negotiable).

    Raises LLMError for every other failure mode (credential rejection,
    transport/provider failure, malformed provider response, or an exhausted
    validation retry). LLMError.usage carries every attempt made before the
    raise, so tokens spent on a failed call are never silently dropped —
    one entry if the first attempt itself failed, two if a schema-invalid
    first attempt triggered a retry that also failed.
    """
    api_key = _resolve_key(settings)
    if api_key is None:
        return MeasuredResult(None, [])

    response_schema = _response_schema(schema)
    schema_block = json.dumps(response_schema)
    first_user = f"{user}\n\nRespond with JSON matching this schema:\n{schema_block}"

    text, usage1 = _call_gemini(api_key, system, first_user, response_schema, model)
    try:
        value = schema.model_validate(_extract_json(text))
        return MeasuredResult(value, [usage1])
    except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as first_error:
        retry_user = (
            f"{first_user}\n\nYour previous response was:\n{text}\n\n"
            f"Your previous response failed validation: {first_error}. "
            "Return only JSON matching the schema above."
        )
        try:
            text2, usage2 = _call_gemini(api_key, system, retry_user, response_schema, model)
        except LLMError as exc:
            exc.usage = [usage1, *exc.usage]
            raise
        try:
            value = schema.model_validate(_extract_json(text2))
            return MeasuredResult(value, [usage1, usage2])
        except (ValidationError, ValueError, KeyError, json.JSONDecodeError) as second_error:
            raise LLMError(
                LLMErrorKind.ERROR,
                f"model output failed validation twice: {second_error}",
                usage=[usage1, usage2],
            ) from second_error


def generate_structured(
    schema: type[BaseModel],
    system: str,
    user: str,
    settings: dict[str, str],
) -> BaseModel | None:
    """Backward-compatible wrapper: the exact pre-Slice-6 signature and
    return type. Every Slice 2-5 caller keeps working unchanged; none of
    them look at usage, which generate_structured_with_usage still collects
    but this wrapper discards."""
    return generate_structured_with_usage(schema, system, user, settings).value
