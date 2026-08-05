"""Provider selection and transport contracts independent of live services."""
from __future__ import annotations

import json

import pytest

from memcommit.provider_types import OLLAMA_PROVIDER, OPENROUTER_PROVIDER
from memcommit.query_provider import QueryProviderError
from memcommit.semantic_provider import (
    OllamaProvider,
    OpenRouterProvider,
    connect_provider,
)


def test_ollama_rejects_non_loopback_endpoint_before_request():
    calls = []

    with pytest.raises(QueryProviderError, match="loopback"):
        OllamaProvider.connect(
            model="qwen3.6:35b-a3b",
            base_url="https://models.example.test",
            requester=lambda *args: calls.append(args),
        )

    assert calls == []


def test_ollama_requires_exact_installed_model():
    def requester(url, method, payload, headers, timeout, operation):
        if url.endswith("/api/version"):
            return {"version": "0.30.10"}
        return {"models": [{"name": "qwen3.6:other", "digest": "a" * 64}]}

    with pytest.raises(QueryProviderError, match="is not installed"):
        OllamaProvider.connect(
            model="qwen3.6:35b-a3b",
            requester=requester,
        )


def test_ollama_completion_sends_schema_as_format_and_trusted_instruction():
    calls = []

    def requester(url, method, payload, headers, timeout, operation):
        calls.append((url, method, payload, headers, timeout, operation))
        if url.endswith("/api/version"):
            return {"version": "0.30.10"}
        if url.endswith("/api/tags"):
            return {
                "models": [
                    {
                        "name": "qwen3.6:35b-a3b",
                        "digest": "b" * 64,
                    }
                ]
            }
        return {
            "model": "qwen3.6:35b-a3b",
            "message": {"role": "assistant", "content": '{"status":"READY"}'},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 41,
            "eval_count": 7,
        }

    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["READY"]}},
        "required": ["status"],
        "additionalProperties": False,
    }
    provider = OllamaProvider.connect(
        model="qwen3.6:35b-a3b",
        context_tokens=32_768,
        max_output_tokens=2_048,
        requester=requester,
    )

    raw = provider.complete(
        "synthetic input",
        operation="test",
        output_schema=schema,
    )

    assert raw == '{"status":"READY"}'
    assert provider.identity.provider == OLLAMA_PROVIDER
    assert provider.identity.model_digest == "b" * 64
    assert provider.last_run is not None
    assert provider.last_run.prompt_tokens == 41
    request_payload = calls[-1][2]
    assert request_payload["format"] == schema
    assert request_payload["think"] is False
    assert request_payload["options"] == {
        "temperature": 0,
        "num_ctx": 32_768,
        "num_predict": 2_048,
    }
    messages = request_payload["messages"]
    assert messages[-1] == {"role": "user", "content": "synthetic input"}
    assert "OUTPUT JSON SCHEMA" in messages[0]["content"]
    assert json.dumps(schema, separators=(",", ":"), sort_keys=True) in messages[0]["content"]


def test_ollama_truncated_completion_fails_closed():
    provider = OllamaProvider(
        model="qwen",
        base_url="http://127.0.0.1:11434",
        identity=None,  # type: ignore[arg-type]
        _requester=lambda *args: {
            "message": {"content": "{}"},
            "done_reason": "length",
        },
    )

    with pytest.raises(QueryProviderError, match="output budget"):
        provider.complete("input", operation="test", output_schema={})


def test_ollama_auto_enables_advertised_thinking_capability():
    payloads = []

    def requester(url, method, payload, headers, timeout, operation):
        if url.endswith("/api/version"):
            return {"version": "test"}
        if url.endswith("/api/tags"):
            return {"models": [{"name": "qwen", "digest": "c" * 64}]}
        if url.endswith("/api/show"):
            return {"capabilities": ["completion", "thinking"]}
        payloads.append(payload)
        return {"message": {"content": "{}"}, "done_reason": "stop"}

    provider = OllamaProvider.connect(model="qwen", requester=requester)
    provider.complete("input", operation="test", output_schema={})

    assert provider.thinking is True
    assert payloads[-1]["think"] is True


def test_openrouter_authenticates_before_completion_and_disables_routing_fallbacks():
    calls = []

    def requester(url, method, payload, headers, timeout, operation):
        calls.append((url, method, payload, headers, timeout, operation))
        if url.endswith("/key"):
            return {"data": {"label": "test-key"}}
        return {
            "model": "qwen/qwen3.5-27b",
            "provider": "example-upstream",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": '{"status":"READY"}'},
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 5},
        }

    schema = {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": ["READY"]}},
        "required": ["status"],
        "additionalProperties": False,
    }
    provider = OpenRouterProvider.connect(
        model="qwen/qwen3.5-27b",
        api_key="secret",
        zdr=True,
        requester=requester,
    )
    raw = provider.complete("synthetic", operation="test", output_schema=schema)

    assert raw == '{"status":"READY"}'
    assert calls[0][0].endswith("/key")
    request_payload = calls[-1][2]
    assert request_payload["model"] == "qwen/qwen3.5-27b"
    assert request_payload["provider"] == {
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
    }
    assert request_payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "memcommit_response",
            "strict": True,
            "schema": schema,
        },
    }
    assert provider.identity.provider == OPENROUTER_PROVIDER
    assert provider.last_run is not None
    assert provider.last_run.upstream_provider == "example-upstream"


def test_openrouter_missing_key_refuses_before_request():
    calls = []

    with pytest.raises(QueryProviderError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider.connect(
            model="qwen/qwen3.5-27b",
            api_key="",
            requester=lambda *args: calls.append(args),
        )

    assert calls == []


class _FakeConfig:
    def require_semantic_model(self):
        return "qwen3.6:35b-a3b"

    def ollama_base_url(self):
        return "http://127.0.0.1:11434"

    def semantic_timeout_seconds(self):
        return 30.0

    def semantic_context_tokens(self):
        return 4096

    def semantic_max_output_tokens(self):
        return 1024

    def semantic_thinking(self):
        return False

    def openrouter_zdr(self):
        return False


def test_connect_provider_rejects_unallowlisted_name_without_execution():
    with pytest.raises(QueryProviderError, match="Unsupported semantic provider"):
        connect_provider("../../executable", config=_FakeConfig())  # type: ignore[arg-type]
