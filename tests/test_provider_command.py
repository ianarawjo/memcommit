"""Provider CLI exposes read-only overviews and explicit route actions."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.config as config_module
from memcommit.adapters.console.entrypoint import app
from memcommit.infrastructure.providers.policy import (
    STUDY_PROVIDER_POLICY_DIGEST,
    STUDY_PROVIDER_POLICY_VERSION,
    ResolvedProviderPolicy,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
)
from memcommit.provider_types import ProviderIdentity


runner = CliRunner(mix_stderr=False)


@pytest.fixture(autouse=True)
def _isolated_profile_and_config(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / ".mem" / "config.json")


def _write_study_registry() -> ProfileEntry:
    profile = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="pilot-001",
        kind="MANAGED",
        source={
            "kind": "STUDY_RUN",
            "study_uid": str(uuid.uuid4()),
            "study_name": "pilot-001",
            "created_at": "2026-08-22T12:00:00+00:00",
            "baseline_sha256": "0" * 64,
            "baseline_profile_uid": str(uuid.uuid4()),
            "baseline_profile_name": "study-baseline",
            "provider_policy_version": STUDY_PROVIDER_POLICY_VERSION,
            "provider_policy_digest": STUDY_PROVIDER_POLICY_DIGEST,
        },
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=profile.uid,
        profiles=(
            ProfileEntry(
                uid=AUTHORING_PROFILE_UID,
                name=AUTHORING_PROFILE_NAME,
                kind="AUTHORING",
            ),
            profile,
        ),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(registry.to_dict()), encoding="utf-8")
    return profile


def _route_payloads() -> list[dict[str, object]]:
    route_dir = profile_registry_file().parent / "provider-routes"
    paths = list(route_dir.glob("*.json")) if route_dir.exists() else []
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def test_bare_provider_shows_active_general_profile_routes(tmp_path):
    config_path = config_module.CONFIG_FILE
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            {
                "semantic_provider": "ollama",
                "semantic_model": "local-model",
                "ollama_model": "local-model",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["provider"])

    assert result.exit_code == 0, result.output
    assert "Usage:" not in result.output
    assert "PROFILE PROVIDER ROUTES" in result.output
    assert "profile: authoring" in result.output
    assert "mode: general · editable" in result.output
    assert "contact_status: not_contacted" in result.output
    assert "ollama · model local-model" in result.output
    assert "source: global_default" in result.output
    assert "operation_routes:\n  none configured" in result.output
    assert "rule:" not in result.output
    assert "fixed by operation" not in result.output


def test_provider_help_remains_explicit_syntax_help():
    result = runner.invoke(app, ["provider", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output
    assert "provider [OPTIONS] COMMAND" in result.output
    assert "PROFILE PROVIDER ROUTES" not in result.output


def test_use_ollama_records_profile_default_and_machine_transport():
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

    assert result.exit_code == 0, result.output
    assert "Profile provider route: authoring · default" in result.output
    payload = _route_payloads()[0]
    assert payload["default"] == {
        "provider": "ollama",
        "model": "qwen3.6:35b-a3b",
        "reasoning_effort": None,
        "timeout_seconds": 600.0,
    }
    assert payload["operations"] == {}
    assert json.loads(config_module.CONFIG_FILE.read_text()) == {
        "llm_model": "qwen3.6:35b-a3b",
        "semantic_thinking": "auto",
        "semantic_context_tokens": "65536",
    }


def test_use_can_configure_and_reset_one_operation_route():
    selected = runner.invoke(
        app,
        [
            "provider",
            "use",
            "codex_chatgpt",
            "--model",
            "gpt-5.6-terra",
            "--reasoning",
            "low",
            "--operation",
            "search",
            "--timeout-seconds",
            "75",
        ],
    )

    assert selected.exit_code == 0, selected.output
    assert "authoring · operation search" in selected.output
    status = runner.invoke(
        app,
        ["provider", "status", "--operation", "search"],
    )
    assert status.exit_code == 0, status.output
    assert "route_source: profile_operation" in status.output
    assert "model: gpt-5.6-terra" in status.output
    assert "reasoning: low" in status.output
    assert "timeout_seconds: 75" in status.output

    reset = runner.invoke(
        app,
        ["provider", "reset", "--operation", "search"],
    )
    assert reset.exit_code == 0, reset.output
    assert _route_payloads()[0]["operations"] == {}


@pytest.mark.parametrize("operation", ["memory", " search ", "SEARCH"])
def test_provider_commands_reject_unknown_or_nonexact_operation_names(operation):
    results = (
        runner.invoke(
            app,
            [
                "provider",
                "use",
                "codex_chatgpt",
                "--operation",
                operation,
            ],
        ),
        runner.invoke(app, ["provider", "status", "--operation", operation]),
        runner.invoke(app, ["provider", "probe", "--operation", operation]),
        runner.invoke(app, ["provider", "reset", "--operation", operation]),
    )

    assert all(result.exit_code == 1 for result in results)
    assert all("one exact supported name" in result.stderr for result in results)
    assert _route_payloads() == []


def test_switching_provider_requires_a_fresh_model():
    result = runner.invoke(app, ["provider", "use", "openrouter"])

    assert result.exit_code != 0
    assert "--model is required" in result.stderr
    assert _route_payloads() == []


def test_codex_preset_is_expanded_into_the_profile_route():
    result = runner.invoke(
        app,
        ["provider", "use", "codex_chatgpt", "--preset", "luna-low"],
    )

    assert result.exit_code == 0, result.output
    assert "model gpt-5.6-luna" in result.output
    assert "reasoning low" in result.output
    assert "preset expanded: luna-low" in result.output
    assert _route_payloads()[0]["default"] == {
        "provider": "codex_chatgpt",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "timeout_seconds": 600.0,
    }


def test_study_overview_is_locked_and_ignores_machine_default():
    _write_study_registry()
    config_module.CONFIG_FILE.parent.mkdir(parents=True)
    config_module.CONFIG_FILE.write_text(
        json.dumps(
            {
                "semantic_provider": "ollama",
                "semantic_model": "mutable-model",
                "ollama_model": "mutable-model",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["provider"])

    assert result.exit_code == 0, result.output
    assert "profile: pilot-001" in result.output
    assert "mode: study · locked" in result.output
    assert f"study_config: {STUDY_PROVIDER_POLICY_VERSION}" in result.output
    assert "reasoning none · tier fast · timeout 600s" in result.output
    assert "search            codex_chatgpt · model gpt-5.6-terra" in result.output
    assert "query             codex_chatgpt · model gpt-5.6-sol" in result.output
    assert "rule:" not in result.output
    assert "configure: unavailable in a Study Profile" in result.output


def test_study_rejects_provider_edits_without_writing_a_route():
    _write_study_registry()

    result = runner.invoke(
        app,
        ["provider", "use", "ollama", "--model", "qwen:latest"],
    )

    assert result.exit_code == 1
    assert "fixed for this Study Profile" in result.stderr
    assert _route_payloads() == []


def test_status_never_prints_openrouter_key(monkeypatch):
    selected = runner.invoke(
        app,
        [
            "provider",
            "use",
            "openrouter",
            "--model",
            "qwen/qwen3.5-27b",
        ],
    )
    assert selected.exit_code == 0, selected.output
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key-value")

    result = runner.invoke(app, ["provider", "status"])

    assert result.exit_code == 0, result.output
    assert "api_key: available" in result.output
    assert "secret-key-value" not in result.output


def test_probe_requires_exact_synthetic_contract(monkeypatch):
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
        source="PROFILE_DEFAULT",
    )
    monkeypatch.setattr(
        "memcommit.commands.provider.command.connect_operation_provider",
        lambda operation, **_kwargs: (FakeProvider(), policy),
    )

    result = runner.invoke(app, ["provider", "probe"])

    assert result.exit_code == 0, result.output
    assert "Provider ready: ollama:test" in result.output
    assert "profile: authoring" in result.output
    assert "probe_scope: profile_default" in result.output
    assert "route_source: profile_default" in result.output


def test_probe_can_follow_one_effective_operation_route(monkeypatch):
    connected: list[str] = []

    class FakeProvider:
        identity = ProviderIdentity(
            provider="codex_chatgpt",
            model="gpt-5.6-terra",
        )

        def complete(self, prompt, *, operation, output_schema=None):
            return '{"status":"READY","echo":"memcommit-provider-probe"}'

    policy = ResolvedProviderPolicy(
        operation="search",
        mode="PRODUCTION",
        provider_id="codex_chatgpt",
        model="gpt-5.6-terra",
        reasoning_effort="low",
        timeout_seconds=600,
        source="PROFILE_OPERATION",
    )

    def connect(operation, **_kwargs):
        connected.append(operation)
        return FakeProvider(), policy

    monkeypatch.setattr(
        "memcommit.commands.provider.command.connect_operation_provider",
        connect,
    )

    result = runner.invoke(
        app,
        ["provider", "probe", "--operation", "search"],
    )

    assert result.exit_code == 0, result.output
    assert connected == ["search"]
    assert "probe_scope: operation search" in result.output
    assert "route_source: profile_operation" in result.output
