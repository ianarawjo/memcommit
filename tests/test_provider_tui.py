"""Profile-aware Provider TUI selection, lock, and exact-review contracts."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.commands.provider as provider_command
import memcommit.config as config_module
from memcommit.cli import app
from memcommit.interfaces.tui.components.exact_command_review import (
    format_exact_command,
)
from memcommit.interfaces.tui.operations.provider import (
    ProviderRouteView,
    ProviderTuiAction,
    ProviderTuiSetup,
    ProviderUseDraft,
    provider_reset_exact_command_review,
    provider_use_exact_command_review,
    run_provider_tui,
)


runner = CliRunner(mix_stderr=False)


def _general_setup() -> ProviderTuiSetup:
    return ProviderTuiSetup(
        profile_name="authoring",
        mode="GENERAL",
        default_route=ProviderRouteView(
            "codex_chatgpt",
            "gpt-5.6-sol",
            "none",
            600,
        ),
        route_source="PROFILE_DEFAULT",
        operation_routes=(
            (
                "search",
                ProviderRouteView(
                    "codex_chatgpt",
                    "gpt-5.6-terra",
                    "low",
                    75,
                ),
            ),
        ),
        has_profile_default=True,
        known_models=(
            ("codex_chatgpt", "gpt-5.6-sol"),
            ("ollama", None),
            ("openrouter", "qwen/qwen3.5-27b"),
        ),
        ollama_thinking="on",
        openrouter_zdr=True,
    )


def _study_setup() -> ProviderTuiSetup:
    return ProviderTuiSetup(
        profile_name="pilot-001",
        mode="STUDY",
        default_route=ProviderRouteView(
            "codex_chatgpt",
            "gpt-5.6-sol",
            "none",
            600,
        ),
        route_source="STUDY_POLICY",
        operation_routes=(
            (
                "search",
                ProviderRouteView(
                    "codex_chatgpt",
                    "gpt-5.6-terra",
                    "low",
                    600,
                ),
            ),
        ),
        study_policy_version="study-provider-config-v1",
        study_policy_digest="a" * 64,
    )


def test_general_tui_selects_ollama_model_and_preserves_thinking() -> None:
    with create_pipe_input() as pipe_input:
        # Down stages Ollama, Enter opens Model, then two Enter transitions
        # reach the reviewed exact command before the final Apply Enter.
        pipe_input.send_text("\x1b[B\r\x15qwen3.6:35b-a3b\r\r\r")
        result = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == ProviderTuiAction(
        "USE",
        draft=ProviderUseDraft(
            "ollama",
            "qwen3.6:35b-a3b",
            None,
            None,
            ollama_thinking="on",
            openrouter_zdr=True,
        ),
    )


def test_general_tui_configures_one_codex_operation_route() -> None:
    with create_pipe_input() as pipe_input:
        # Enter Model, replace it, choose LOW, then type an operation key and
        # approve only after the exact command surface owns focus.
        pipe_input.send_text("\r\x15gpt-5.6-terra\r\x1b[C\x1b[C\rsearch\r\r")
        result = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == ProviderTuiAction(
        "USE",
        draft=ProviderUseDraft(
            "codex_chatgpt",
            "gpt-5.6-terra",
            "low",
            "search",
            ollama_thinking="on",
            openrouter_zdr=True,
        ),
    )


def test_general_tui_reviews_reset_for_one_authored_operation() -> None:
    with create_pipe_input() as pipe_input:
        # Tab follows Provider, Model, Reasoning, Operation, and To Do. R swaps
        # the pending exact action without writing, then Enter approves it.
        pipe_input.send_text("\t\t\tsearch\tr\r")
        result = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result == ProviderTuiAction("RESET", operation="search")


def test_general_tui_incomplete_external_model_cannot_apply() -> None:
    with create_pipe_input() as pipe_input:
        # OpenRouter has a known model in setup, so clear it before reaching To
        # Do. Enter reports an incomplete route; two Esc presses back out safely.
        pipe_input.send_text("\x1b[B\x1b[B\t\x15\t\t\r\x1b\x1b")
        result = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is None


def test_general_tui_probe_and_cancel_publish_no_use_draft() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("p")
        probed = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        cancelled = run_provider_tui(
            _general_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert probed == ProviderTuiAction("PROBE")
    assert cancelled is None


def test_study_tui_exposes_only_probe_or_close() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        probed = run_provider_tui(
            _study_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        closed = run_provider_tui(
            _study_setup(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert probed == ProviderTuiAction("PROBE")
    assert closed is None


def test_exact_reviews_preserve_provider_specific_transport_state() -> None:
    setup = _general_setup()
    use = provider_use_exact_command_review(
        setup,
        ProviderUseDraft(
            "openrouter",
            "qwen/qwen3.5-27b",
            None,
            "search",
            openrouter_zdr=True,
        ),
    )
    reset = provider_reset_exact_command_review(setup, operation="search")

    assert format_exact_command(use) == (
        "mem provider use openrouter --model qwen/qwen3.5-27b --zdr "
        "--operation search"
    )
    assert format_exact_command(reset) == "mem provider reset --operation search"
    assert any("Do not contact the provider" in effect for effect in use.effects)


def test_bare_tty_provider_reenters_the_existing_use_command_boundary(
    monkeypatch,
    tmp_path,
) -> None:
    action = ProviderTuiAction(
        "USE",
        draft=ProviderUseDraft(
            "ollama",
            "qwen:latest",
            None,
            None,
            ollama_thinking="off",
        ),
    )
    observed: list[tuple[object, ...]] = []
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(provider_command, "is_interactive_terminal", lambda: True)
    monkeypatch.setattr(
        provider_command,
        "_provider_tui_setup",
        lambda _config: _general_setup(),
    )
    monkeypatch.setattr(
        provider_command,
        "run_provider_tui",
        lambda _setup: action,
    )
    monkeypatch.setattr(
        provider_command,
        "use_provider",
        lambda provider, **values: observed.append((provider, values)),
    )

    result = runner.invoke(app, ["provider"])

    assert result.exit_code == 0, result.output
    assert observed == [
        (
            "ollama",
            {
                "model": "qwen:latest",
                "preset": None,
                "reasoning": None,
                "operation": None,
                "timeout_seconds": None,
                "context_tokens": None,
                "max_output_tokens": None,
                "thinking": "off",
                "zdr": False,
            },
        )
    ]
