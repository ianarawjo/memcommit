"""Codex/ChatGPT subscription provider safety contracts."""

import json
import subprocess
from pathlib import Path

import pytest

from memcommit.providers.subscription import (
    CodexChatGPTProvider,
    QueryProviderError,
    connect_query_provider,
    resolve_codex_binary,
)


def _completed(args, returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=args,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.mark.parametrize(
    "variable",
    ["OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN"],
)
def test_auth_override_refuses_before_running_any_process(variable):
    calls = []

    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        pytest.fail("no subprocess should run with an auth override")

    with pytest.raises(QueryProviderError, match=variable):
        CodexChatGPTProvider.connect(
            env={variable: "secret-value"},
            candidates=[Path("/working/codex")],
            runner=runner,
        )

    assert calls == []


def test_connect_requires_exact_chatgpt_status_and_sanitizes_environment():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        if args[-1] == "--version":
            return _completed(args, stdout="codex-cli 1.2.3\n")
        return _completed(
            args,
            stdout="warning\nLogged in using ChatGPT\n",
        )

    provider = CodexChatGPTProvider.connect(
        env={
            "CODEX_HOME": "/auth/home",
            "OPENAI_API_KEY": "",
            "CODEX_API_KEY": "",
            "CODEX_ACCESS_TOKEN": "",
        },
        candidates=[Path("/working/codex")],
        runner=runner,
    )

    assert provider.binary == Path("/working/codex")
    assert provider.env["CODEX_HOME"] == "/auth/home"
    assert provider.env["NO_COLOR"] == "1"
    assert provider.env["RUST_LOG"] == "error"
    assert all(
        name not in provider.env
        for name in (
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "CODEX_ACCESS_TOKEN",
        )
    )
    assert calls[1][0] == ["/working/codex", "login", "status"]


def test_connect_rejects_api_key_login():
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        if args[-1] == "--version":
            return _completed(args, stdout="codex-cli 1.2.3")
        return _completed(args, stdout="Logged in using an API key")

    with pytest.raises(QueryProviderError, match="logged in using ChatGPT"):
        CodexChatGPTProvider.connect(
            env={},
            candidates=[Path("/working/codex")],
            runner=runner,
        )

    assert len(calls) == 2


def test_binary_resolver_skips_a_broken_candidate():
    calls = []

    def runner(args, **kwargs):
        calls.append(args[0])
        if args[0] == "/broken/codex":
            return _completed(args, returncode=1, stderr="ENOENT")
        return _completed(args, stdout="codex-cli 9.9.9")

    selected = resolve_codex_binary(
        candidates=[Path("/broken/codex"), Path("/working/codex")],
        env={},
        runner=runner,
    )

    assert selected == Path("/working/codex")
    assert calls == ["/broken/codex", "/working/codex"]


def test_binary_resolver_normalizes_relative_candidate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    selected = resolve_codex_binary(
        candidates=[Path("bin/codex")],
        env={},
        runner=lambda args, **kwargs: _completed(
            args,
            stdout="codex-cli 9.9.9",
        ),
    )

    assert selected == tmp_path / "bin" / "codex"


def test_query_uses_stdin_and_ephemeral_read_only_temp_directory(tmp_path):
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        captured["cwd_exists_during_call"] = Path(kwargs["cwd"]).is_dir()
        return _completed(args, stdout="Supported answer.\n", stderr="progress")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={"CODEX_HOME": "/auth/home"},
        _runner=runner,
    )
    source = "PRIVATE SOURCE VALUE"
    question = "What is supported?"

    answer = provider.query("agreements", source, question)

    args = captured["args"]
    kwargs = captured["kwargs"]
    assert answer == "Supported answer."
    assert captured["cwd_exists_during_call"] is True
    assert not Path(kwargs["cwd"]).exists()
    assert args[-1] == "-"
    assert "--ephemeral" in args
    assert "--ignore-user-config" in args
    assert "--ignore-rules" in args
    assert "--skip-git-repo-check" in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--cd") + 1] == kwargs["cwd"]
    assert 'shell_environment_policy.inherit="none"' in args
    assert source not in " ".join(args)
    assert question not in " ".join(args)
    assert source in kwargs["input"]
    assert question in kwargs["input"]
    assert kwargs["env"] == {"CODEX_HOME": "/auth/home"}


def test_complete_writes_output_schema_only_inside_temporary_directory():
    captured = {}
    schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    }

    def runner(args, **kwargs):
        schema_path = Path(args[args.index("--output-schema") + 1])
        captured["schema_path"] = schema_path
        captured["schema"] = json.loads(schema_path.read_text())
        captured["inside_temp"] = schema_path.parent == Path(kwargs["cwd"])
        return _completed(args, stdout="{}")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        _runner=runner,
    )

    result = provider.complete(
        "prompt",
        operation="find",
        output_schema=schema,
    )

    assert result == "{}"
    assert captured["schema"] == schema
    assert captured["inside_temp"] is True
    assert not captured["schema_path"].exists()


def test_complete_pins_explicit_codex_model_and_reasoning():
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        return _completed(args, stdout="READY")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        model="gpt-5.6-luna",
        reasoning_effort="low",
        _runner=runner,
    )

    assert provider.complete("prompt", operation="probe") == "READY"

    args = captured["args"]
    assert args[args.index("--model") + 1] == "gpt-5.6-luna"
    assert 'model_reasoning_effort="low"' in args
    assert provider.identity.model == "gpt-5.6-luna"
    assert provider.identity.reasoning_effort == "low"
    assert provider.last_run is not None
    assert provider.last_run.upstream_model == "gpt-5.6-luna"


def test_complete_enables_fast_tier_explicitly_despite_ignored_user_config():
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        return _completed(args, stdout="READY")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        model="gpt-5.6-sol",
        reasoning_effort="none",
        service_tier="fast",
        _runner=runner,
    )

    assert provider.complete("prompt", operation="probe") == "READY"

    args = captured["args"]
    assert "--ignore-user-config" in args
    assert 'service_tier="fast"' in args
    assert "features.fast_mode=true" in args
    assert provider.identity.runtime == "codex-cli/fast"


def test_codex_provider_rejects_unknown_service_tier():
    with pytest.raises(QueryProviderError, match="service tier"):
        CodexChatGPTProvider(
            binary=Path("/working/codex"),
            env={},
            service_tier="ultrafast",
        )


def test_complete_forwards_documented_none_reasoning_effort():
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        return _completed(args, stdout="READY")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        model="gpt-5.6-sol",
        reasoning_effort="none",
        _runner=runner,
    )

    assert provider.complete("prompt", operation="probe") == "READY"
    assert 'model_reasoning_effort="none"' in captured["args"]
    assert provider.identity.reasoning_effort == "none"


def test_complete_forwards_documented_max_reasoning_effort():
    captured = {}

    def runner(args, **kwargs):
        captured["args"] = args
        return _completed(args, stdout="READY")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        model="gpt-5.6-luna",
        reasoning_effort="max",
        _runner=runner,
    )

    assert provider.complete("prompt", operation="probe") == "READY"
    assert 'model_reasoning_effort="max"' in captured["args"]
    assert provider.identity.reasoning_effort == "max"


def test_query_failure_does_not_expose_prompt_or_stderr():
    secret = "DO NOT EXPOSE THIS"

    def runner(args, **kwargs):
        return _completed(args, returncode=7, stderr=f"failure: {secret}")

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        _runner=runner,
    )

    with pytest.raises(QueryProviderError) as exc:
        provider.query("source", secret, "question containing private detail")

    message = str(exc.value)
    assert "exit 7" in message
    assert secret not in message
    assert "private detail" not in message


def test_query_timeout_cleans_up_temporary_directory():
    captured = {}

    def runner(args, **kwargs):
        captured["cwd"] = kwargs["cwd"]
        raise subprocess.TimeoutExpired(args, timeout=1)

    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        _runner=runner,
    )

    with pytest.raises(QueryProviderError, match="timed out after 120 seconds"):
        provider.query("source", "text", "question")

    assert not Path(captured["cwd"]).exists()


def test_query_rejects_empty_success_output():
    provider = CodexChatGPTProvider(
        binary=Path("/working/codex"),
        env={},
        _runner=lambda args, **kwargs: _completed(args, stdout=" \n"),
    )

    with pytest.raises(QueryProviderError, match="no answer"):
        provider.query("source", "text", "question")


def test_unknown_provider_is_not_executed():
    with pytest.raises(QueryProviderError, match="Unsupported query provider"):
        connect_query_provider("../../arbitrary-executable")
