"""Concrete OpenAI Responses API client for bounded trading advice."""

import http.client
import json
from collections.abc import Mapping
from typing import Protocol, cast

from fx_platform.adapters.ai.openai import AiProviderError

_OPENAI_HOST = "api.openai.com"
_OPENAI_PATH = "/v1/responses"
_SYSTEM_INSTRUCTIONS = (
    "You are a constrained FX market advisory component. Analyze only the supplied point-in-time "
    "market snapshot and deterministic candidate. Never request tools, never place or modify an "
    "order, never change volume/SL/TP, and never invent external news or market data. Return only "
    "the requested structured assessment. Prefer neutral/high uncertainty when evidence is weak."
)

_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "direction_preference": {
            "type": "string",
            "enum": ["buy", "sell", "neutral"],
        },
        "confidence": {
            "type": "string",
            "pattern": r"^(?:0(?:\.\d+)?|1(?:\.0+)?)$",
        },
        "market_regime": {
            "type": "string",
            "enum": ["trending", "ranging", "volatile", "uncertain"],
        },
        "uncertainty": {
            "type": "string",
            "pattern": r"^(?:0(?:\.\d+)?|1(?:\.0+)?)$",
        },
        "reasoning_tags": {
            "type": "array",
            "maxItems": 16,
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
        },
    },
    "required": [
        "direction_preference",
        "confidence",
        "market_regime",
        "uncertainty",
        "reasoning_tags",
    ],
}


class ResponsesTransport(Protocol):
    """Injectable HTTPS boundary used to keep tests offline."""

    def __call__(
        self,
        *,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        """POST one Responses API request and return decoded JSON."""
        ...


def _post_responses_api(
    *,
    body: bytes,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> Mapping[str, object]:
    connection = http.client.HTTPSConnection(_OPENAI_HOST, timeout=timeout_seconds)
    try:
        connection.request("POST", _OPENAI_PATH, body=body, headers=dict(headers))
        response = connection.getresponse()
        raw = response.read()
    except (OSError, TimeoutError, http.client.HTTPException) as error:
        raise AiProviderError("OpenAI transport unavailable") from error
    finally:
        connection.close()

    if response.status < 200 or response.status >= 300:
        raise AiProviderError(f"OpenAI returned HTTP {response.status}")
    try:
        decoded: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AiProviderError("OpenAI returned invalid JSON") from error
    if not isinstance(decoded, dict):
        raise AiProviderError("OpenAI returned a non-object response")
    return cast(Mapping[str, object], decoded)


def _extract_output_text(response: Mapping[str, object]) -> str:
    if response.get("status") != "completed":
        raise AiProviderError("OpenAI response did not complete")
    output = response.get("output")
    if not isinstance(output, list):
        raise AiProviderError("OpenAI response output is missing")
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text:
                return text
    raise AiProviderError("OpenAI response contained no output text")


class OpenAiResponsesClient:
    """Call the Responses API with a strict JSON schema and no tool authority."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 8.0,
        transport: ResponsesTransport = _post_responses_api,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        if not model:
            raise ValueError("model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def create_assessment(self, payload: Mapping[str, object]) -> Mapping[str, object]:
        """Request one schema-constrained advisory assessment."""
        request_body = {
            "model": self._model,
            "instructions": _SYSTEM_INSTRUCTIONS,
            "input": json.dumps(payload, separators=(",", ":"), sort_keys=True),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "fx_ai_assessment",
                    "strict": True,
                    "schema": _RESPONSE_SCHEMA,
                }
            },
            "max_output_tokens": 256,
            "store": False,
        }
        encoded = json.dumps(request_body, separators=(",", ":")).encode("utf-8")
        response = self._transport(
            body=encoded,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout_seconds=self._timeout_seconds,
        )
        output_text = _extract_output_text(response)
        try:
            decoded: object = json.loads(output_text)
        except json.JSONDecodeError:
            return {}
        if not isinstance(decoded, dict):
            return {}
        return cast(Mapping[str, object], decoded)
