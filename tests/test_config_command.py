"""Configuration CLI defaults to its read-only overview."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

import memcommit.config as config_module
from memcommit.adapters.console.entrypoint import app


runner = CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")


def test_bare_config_matches_explicit_show() -> None:
    config_module.CONFIG_FILE.write_text(
        json.dumps({"semantic_provider": "ollama", "llm_model": "qwen:latest"}),
        encoding="utf-8",
    )

    bare = runner.invoke(app, ["config"])
    explicit = runner.invoke(app, ["config", "show"])

    assert bare.exit_code == 0, bare.output
    assert bare.output == explicit.output
    assert "semantic_provider = 'ollama'" in bare.output
    assert "llm_model = 'qwen:latest'" in bare.output


def test_bare_config_reports_an_empty_configuration() -> None:
    result = runner.invoke(app, ["config"])

    assert result.exit_code == 0, result.output
    assert result.output == "(no configuration set)\n"


def test_config_help_remains_explicit_syntax_help() -> None:
    result = runner.invoke(app, ["config", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "config [OPTIONS] COMMAND" in result.output
    assert "(no configuration set)" not in result.output
