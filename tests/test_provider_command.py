"""CLI selection remains explicit, coherent, and credential-free."""
from __future__ import annotations

import json

from typer.testing import CliRunner

import memcommit.config as config_module
from memcommit.cli import app
from memcommit.provider_types import ProviderIdentity


runner = CliRunner(mix_stderr=False)


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
    assert "Semantic provider: ollama" in result.output
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


def test_probe_requires_exact_synthetic_contract(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")

    class FakeProvider:
        identity = ProviderIdentity(provider="ollama", model="test")

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "provider probe"
            assert output_schema is not None
            return '{"status":"READY","echo":"memcommit-provider-probe"}'

    monkeypatch.setattr(
        "memcommit.commands.provider.connect_semantic_provider",
        lambda: FakeProvider(),
    )

    result = runner.invoke(app, ["provider", "probe"])

    assert result.exit_code == 0
    assert "Provider ready: ollama:test" in result.output
