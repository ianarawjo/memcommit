"""Choose a provider or edit its configuration through CLI and one shared TUI."""

import os
import subprocess
from typing import Annotated

import typer

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup
from memcommit.adapters.console.commands.llm_provider.preparation import (
    ProviderPreparationCancelled,
    prepare_codex_catalog,
)
from memcommit.adapters.console.commands.llm_provider.screen import (
    run_provider_configuration_screen,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    is_interactive_terminal,
    require_interactive_terminal,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.configuration.config import Config
from memcommit.application.operations.llm_provider.application import (
    read_codex_configuration,
    save_codex_configuration,
    select_provider,
    reset_codex_configuration,
)
from memcommit.application.operations.llm_provider.codex_configuration import (
    require_configurable_provider,
    select_codex_configuration,
)
from memcommit.application.operations.llm_provider.probe import verify_provider_response
from memcommit.llm_providers.connection import connect_semantic_provider
from memcommit.llm_providers.errors import QueryProviderError
from memcommit.llm_providers.settings import resolve_provider_settings
from memcommit.llm_providers.types import (
    CODEX_CHATGPT_PROVIDER,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
)

app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Choose an LLM provider and configure its model/reasoning.",
)


def _report_configuration_error(error):
    typer.secho(
        f"LLM provider configuration error: {error}", fg=typer.colors.RED, err=True
    )
    raise typer.Exit(1)


def _echo_configuration(configuration):
    typer.echo(f"model: {configuration.model}")
    typer.echo(f"reasoning: {configuration.reasoning_effort or 'provider default'}")


def _show_overview():
    settings = resolve_provider_settings(Config())
    typer.echo("USER LLM PROVIDER SETTINGS")
    typer.echo("scope: user · all Profiles and operations")
    typer.echo("contact_status: not_contacted")
    typer.echo(f"provider: {settings.provider_id}")
    typer.echo(f"model: {settings.model}")
    if settings.provider_id == CODEX_CHATGPT_PROVIDER:
        typer.echo(f"reasoning: {settings.reasoning_effort or 'provider default'}")
    typer.echo("use: mem llm-provider use codex_chatgpt")
    typer.echo(
        "configure: mem llm-provider configure codex_chatgpt --model MODEL --reasoning EFFORT"
    )


def _open_provider_configuration(*, initial_focus="use"):
    require_interactive_terminal(
        "LLM provider configuration",
        snapshot_hint="Use 'mem llm-provider status' or explicit configure flags outside a terminal.",
    )
    config = Config()
    _, catalog = prepare_codex_catalog()
    action = run_provider_configuration_screen(
        catalog,
        saved_configuration=read_codex_configuration(config),
        active_provider=config.get("semantic_provider"),
        initial_focus=initial_focus,
    )
    if action is None:
        typer.echo("LLM provider configuration cancelled. Settings unchanged.")
        return
    if action.kind == "USE":
        select_provider(config, CODEX_CHATGPT_PROVIDER)
        typer.echo("Using LLM provider: codex_chatgpt · all Profiles and operations")
    else:
        selected = select_codex_configuration(
            catalog, action.configuration.model, action.configuration.reasoning_effort
        )
        save_codex_configuration(config, selected)
        typer.echo("Codex configuration saved · all Profiles and operations")
        _echo_configuration(selected)


@app.callback(invoke_without_command=True)
def llm_provider_group(ctx: typer.Context) -> None:
    """Open USE and CONFIGURE together in a TTY; print a summary when piped."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        if is_interactive_terminal():
            _open_provider_configuration()
        else:
            _show_overview()
    except ProviderPreparationCancelled:
        typer.echo("LLM provider preparation cancelled. Settings unchanged.")
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        _report_configuration_error(error)


@app.command("use")
def use_llm_provider(
    provider: Annotated[
        str | None, typer.Argument(metavar="LLM_PROVIDER", help="codex_chatgpt")
    ] = None,
) -> None:
    """Select a saved provider without changing its model or reasoning."""
    try:
        if provider is None:
            _open_provider_configuration()
        else:
            select_provider(Config(), provider)
            typer.echo(f"Using LLM provider: {provider} · all Profiles and operations")
    except ProviderPreparationCancelled:
        typer.echo("LLM provider preparation cancelled. Settings unchanged.")
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        _report_configuration_error(error)


@app.command("configure")
def configure_llm_provider(
    provider: Annotated[
        str, typer.Argument(metavar="LLM_PROVIDER", help="codex_chatgpt")
    ] = CODEX_CHATGPT_PROVIDER,
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Codex model from the environment catalog"),
    ] = None,
    reasoning: Annotated[
        str | None,
        typer.Option(
            "--reasoning", help="Reasoning effort supported by the selected model"
        ),
    ] = None,
) -> None:
    """Edit Codex model/reasoning; preserve the active provider and hidden settings."""
    try:
        require_configurable_provider(provider)
        if model is None and reasoning is None:
            _open_provider_configuration(initial_focus="model")
            return
        config = Config()
        current = read_codex_configuration(config)
        _, catalog = prepare_codex_catalog(interactive=False)
        selected = select_codex_configuration(
            catalog,
            model if model is not None else current.model,
            reasoning
            if reasoning is not None
            else current.reasoning_effort
            if model is None or model == current.model
            else None,
        )
        save_codex_configuration(config, selected)
        typer.echo("Codex configuration saved · all Profiles and operations")
        _echo_configuration(selected)
    except ProviderPreparationCancelled:
        typer.echo("LLM provider preparation cancelled. Settings unchanged.")
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        _report_configuration_error(error)


@app.command("reset")
def reset_llm_provider(
    provider: Annotated[
        str, typer.Argument(metavar="LLM_PROVIDER", help="codex_chatgpt")
    ] = CODEX_CHATGPT_PROVIDER,
) -> None:
    """Restore Codex model/reasoning defaults; preserve provider selection."""
    try:
        require_configurable_provider(provider)
        config = Config()
        reset_codex_configuration(config)
        typer.echo("Codex model/reasoning reset. Provider selection unchanged.")
        _echo_configuration(read_codex_configuration(config))
    except (RuntimeError, ValueError) as error:
        _report_configuration_error(error)


@app.command("status")
def show_llm_provider_status() -> None:
    """Inspect actual shared settings without contacting a provider."""
    config = Config()
    try:
        settings = resolve_provider_settings(config)
        typer.echo("scope: user")
        typer.echo("contact_status: not_contacted")
        typer.echo(f"provider: {settings.provider_id}")
        typer.echo(f"model: {settings.model}")
        typer.echo(f"timeout_seconds: {settings.timeout_seconds:g}")
        if settings.provider_id == CODEX_CHATGPT_PROVIDER:
            typer.echo(f"reasoning: {settings.reasoning_effort or 'provider default'}")
            typer.echo(f"service_tier: {settings.service_tier or 'standard'}")
        elif settings.provider_id == OLLAMA_PROVIDER:
            typer.echo(f"endpoint: {config.ollama_base_url()}")
            typer.echo(f"thinking: {config.semantic_thinking()}")
            typer.echo(f"max_output_tokens: {config.semantic_max_output_tokens()}")
            typer.echo(f"context_tokens: {config.semantic_context_tokens()}")
        elif settings.provider_id == OPENROUTER_PROVIDER:
            typer.echo(f"max_output_tokens: {config.semantic_max_output_tokens()}")
            typer.echo(
                "api_key: "
                + ("available" if os.environ.get("OPENROUTER_API_KEY") else "missing")
            )
            typer.echo(f"zdr: {str(config.openrouter_zdr()).lower()}")
            typer.echo("fallbacks: disabled")
    except (RuntimeError, ValueError) as error:
        _report_configuration_error(error)


@app.command("probe")
def probe_llm_provider() -> None:
    """Verify the active provider with one synthetic strict-schema completion."""
    try:
        with CommandProgress(
            "LLM PROVIDER PROBE", "checking synthetic completion", total=1
        ):
            provider = connect_semantic_provider()
            verify_provider_response(provider)
        typer.echo(f"LLM provider ready: {provider.identity.display_name()}")
        typer.echo("probe_scope: user · all Profiles and operations")
    except (QueryProviderError, RuntimeError, ValueError) as error:
        typer.secho(
            f"LLM provider probe failed: {error}", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)
