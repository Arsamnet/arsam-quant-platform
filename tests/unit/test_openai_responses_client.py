"""Offline tests for the concrete OpenAI Responses API transport boundary."""

import json
from collections.abc import Mapping

import pytest

from fx_platform.adapters.ai import AiProviderError, OpenAiResponsesClient


def _completed_response(text: str) -> Mapping[str, object]:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


def test_responses_client_requests_strict_schema_without_tools() -> None:
    captured: dict[str, object] = {}

    def transport(
        *,
        body: bytes,
        headers: Mapping[str, str],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        captured["body"] = json.loads(body)
        captured["headers"] = dict(headers)
        captured["timeout_seconds"] = timeout_seconds
        return _completed_response(
            json.dumps(
                {
                    "direction_preference": "buy",
                    "confidence": "0.80",
                    "market_regime": "trending",
                    "uncertainty": "0.20",
                    "reasoning_tags": ["trend_alignment"],
                }
            )
        )

    client = OpenAiResponsesClient(
        api_key="test-api-key",
        model="configured-model",
        timeout_seconds=5,
        transport=transport,
    )

    result = client.create_assessment(
        {
            "market": {"symbol": "EURUSD"},
            "candidate": {"side": "buy"},
        }
    )

    assert result["direction_preference"] == "buy"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "configured-model"
    assert body["store"] is False
    assert "tools" not in body
    text = body["text"]
    assert isinstance(text, dict)
    output_format = text["format"]
    assert isinstance(output_format, dict)
    assert output_format["type"] == "json_schema"
    assert output_format["strict"] is True
    assert captured["timeout_seconds"] == 5


def test_responses_client_returns_invalid_mapping_for_non_json_model_text() -> None:
    client = OpenAiResponsesClient(
        api_key="test-api-key",
        model="configured-model",
        transport=lambda **_: _completed_response("not-json"),
    )

    assert client.create_assessment({"market": {}}) == {}


def test_responses_client_propagates_provider_failure() -> None:
    def unavailable(**_: object) -> Mapping[str, object]:
        raise AiProviderError("unavailable")

    client = OpenAiResponsesClient(
        api_key="test-api-key",
        model="configured-model",
        transport=unavailable,
    )

    with pytest.raises(AiProviderError, match="unavailable"):
        client.create_assessment({"market": {}})


@pytest.mark.parametrize(
    ("api_key", "model", "timeout"),
    [
        ("", "model", 8),
        ("key", "", 8),
        ("key", "model", 0),
    ],
)
def test_responses_client_rejects_invalid_configuration(
    api_key: str,
    model: str,
    timeout: float,
) -> None:
    with pytest.raises(ValueError):
        OpenAiResponsesClient(api_key=api_key, model=model, timeout_seconds=timeout)
