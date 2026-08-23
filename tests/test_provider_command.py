"""CLI selection remains explicit, coherent, and credential-free."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.config as config_module
from memcommit.cli import app
from memcommit.infrastructure.providers.policy import ResolvedProviderPolicy
from memcommit.provider_types import ProviderIdentity


runner = CliRunner(mix_stderr=False)


def test_bare_provider_shows_global_and_operation_routing(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "ollama",
                "semantic_model": "local-model",
                "ollama_model": "local-model",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(app, ["provider"])

    assert result.exit_code == 0, result.output
    assert "Usage:" not in result.output
    assert "SEMANTIC PROVIDER ROUTING" in result.output
    assert "config_scope: global · all Profiles" in result.output
    assert "contact_status: not_contacted" in result.output
    assert "global_default:" in result.output
    assert "ollama · model local-model" in result.output
    assert "authored_operation_policies:" in result.output
    assert "search" in result.output
    assert "codex_chatgpt · model gpt-5.6-terra" in result.output
    assert "compare_contexts" in result.output
    assert "rule: inherits global identity · timeout floor 900s" in result.output
    assert "other_operations: inherit global_default" in result.output
    assert json.loads(config_path.read_text())["semantic_provider"] == "ollama"


def test_provider_help_remains_explicit_syntax_help(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    result = runner.invoke(app, ["provider", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "provider [OPTIONS] COMMAND" in result.output
    assert "SEMANTIC PROVIDER ROUTING" not in result.output


def test_use_ollama_records_provider_model_and_legacy_bridge(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(
        app,
        [
            "provider",
            "use",
            "ollama",
            "--model",
            "qwen3.6:35b-a3b",
            "--context-tokens",
            "65536",
        ],
    )

    assert result.exit_code == 0
    assert "Global semantic default: ollama" in result.output
    assert "Scope: all Profiles; operation-specific policies are unchanged." in result.output
    assert json.loads(config_path.read_text()) == {
        "semantic_provider": "ollama",
        "semantic_model": "qwen3.6:35b-a3b",
        "ollama_model": "qwen3.6:35b-a3b",
        "llm_model": "qwen3.6:35b-a3b",
        "semantic_thinking": "auto",
        "semantic_context_tokens": "65536",
    }


def test_switching_provider_requires_a_fresh_model(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "ollama",
                "semantic_model": "qwen3.6:35b-a3b",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(app, ["provider", "use", "openrouter"])

    assert result.exit_code != 0
    assert "--model is required" in result.stderr
    assert json.loads(config_path.read_text())["semantic_provider"] == "ollama"


def test_use_codex_luna_low_preset_records_both_axes(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(
        app,
        ["provider", "use", "codex_chatgpt", "--preset", "luna-low"],
    )

    assert result.exit_code == 0, result.output
    assert "model gpt-5.6-luna" in result.output
    assert "reasoning low" in result.output
    assert json.loads(config_path.read_text()) == {
        "semantic_provider": "codex_chatgpt",
        "semantic_model": "gpt-5.6-luna",
        "codex_chatgpt_model": "gpt-5.6-luna",
        "codex_chatgpt_reasoning_effort": "low",
        "codex_chatgpt_preset": "luna-low",
    }


def test_bare_codex_selection_restores_managed_defaults(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "codex_chatgpt",
                "semantic_model": "gpt-5.6-luna",
                "codex_chatgpt_model": "gpt-5.6-luna",
                "codex_chatgpt_reasoning_effort": "low",
                "codex_chatgpt_preset": "luna-low",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(app, ["provider", "use", "codex_chatgpt"])

    assert result.exit_code == 0, result.output
    saved = json.loads(config_path.read_text())
    assert saved["semantic_provider"] == "codex_chatgpt"
    assert saved["semantic_model"] == ""
    assert saved["codex_chatgpt_model"] == ""
    assert saved["codex_chatgpt_reasoning_effort"] == ""
    assert saved["codex_chatgpt_preset"] == ""


def test_codex_status_shows_explicit_model_reasoning_and_preset(
    monkeypatch,
    tmp_path,
):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "codex_chatgpt",
                "codex_chatgpt_model": "gpt-5.6-luna",
                "codex_chatgpt_reasoning_effort": "low",
                "codex_chatgpt_preset": "luna-low",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(app, ["provider", "status"])

    assert result.exit_code == 0, result.output
    assert "scope: global_default" in result.output
    assert "profile_scope: all_profiles" in result.output
    assert "model: gpt-5.6-luna" in result.output
    assert "reasoning: low" in result.output
    assert "preset: luna-low" in result.output


def test_status_never_prints_openrouter_key(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "openrouter",
                "semantic_model": "qwen/qwen3.5-27b",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key-value")

    result = runner.invoke(app, ["provider", "status"])

    assert result.exit_code == 0
    assert "api_key: available" in result.output
    assert "secret-key-value" not in result.output


def test_pinned_operation_status_hides_unrelated_global_codex_preset(
    monkeypatch,
    tmp_path,
):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "codex_chatgpt",
                "codex_chatgpt_model": "gpt-5.6-luna",
                "codex_chatgpt_reasoning_effort": "low",
                "codex_chatgpt_preset": "luna-low",
            }
        )
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", config_path)

    result = runner.invoke(
        app,
        ["provider", "status", "--operation", "query"],
    )

    assert result.exit_code == 0, result.output
    assert "scope: effective_operation" in result.output
    assert "model: gpt-5.6-sol" in result.output
    assert "reasoning: none" in result.output
    assert "preset:" not in result.output


def test_probe_requires_exact_synthetic_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    class FakeProvider:
        identity = ProviderIdentity(provider="ollama", model="test")

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "provider probe"
            assert output_schema is not None
            return '{"status":"READY","echo":"memcommit-provider-probe"}'

    policy = ResolvedProviderPolicy(
        operation="semantic_default",
        mode="PRODUCTION",
        provider_id="ollama",
        model="test",
        reasoning_effort=None,
        timeout_seconds=600,
        source="GLOBAL_DEFAULT",
    )
    monkeypatch.setattr(
        "memcommit.commands.provider.connect_operation_provider",
        lambda operation: (FakeProvider(), policy),
    )

    result = runner.invoke(app, ["provider", "probe"])

    assert result.exit_code == 0
    assert "Provider ready: ollama:test" in result.output
    assert "probe_scope: global_default" in result.output
    assert "policy_source: global_default" in result.output


def test_probe_can_follow_one_effective_operation_policy(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    connected: list[str] = []

    class FakeProvider:
        identity = ProviderIdentity(provider="codex_chatgpt", model="gpt-5.6-terra")

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "provider probe"
            return '{"status":"READY","echo":"memcommit-provider-probe"}'

    policy = ResolvedProviderPolicy(
        operation="search",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="gpt-5.6-terra",
        reasoning_effort="low",
        timeout_seconds=600,
        source="OPERATION_POLICY",
    )

    def connect(operation):
        connected.append(operation)
        return FakeProvider(), policy

    monkeypatch.setattr(
        "memcommit.commands.provider.connect_operation_provider",
        connect,
    )

    result = runner.invoke(
        app,
        ["provider", "probe", "--operation", "search"],
    )

    assert result.exit_code == 0, result.output
    assert connected == ["search"]
    assert "probe_scope: operation search" in result.output
    assert "policy_source: operation_policy" in result.output
