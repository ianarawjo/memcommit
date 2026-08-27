"""Inspect, edit, and probe the active Profile's semantic-provider routes."""

from __future__ import annotations

import json
import os
from typing import Annotated, Optional

import typer

from memcommit.commands.shared.command_group import CanonicalCommandGroup
from memcommit.commands.shared.command_progress import CommandProgress
from memcommit.configuration.config import Config
from memcommit.providers.policy import (
    POLICY_VERSION,
    ProviderRoute,
    ResolvedProviderPolicy,
    study_provider_config,
)
from memcommit.providers.profile_routes import (
    ProfileProviderRoutesError,
    load_active_provider_scope,
    reset_active_profile_route,
    resolve_active_provider_policy,
    set_active_profile_route,
)
from memcommit.application.operations.profile.config import load_profile_registry
from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_LUNA_LOW_PRESET,
    CODEX_LUNA_MODEL,
    CODEX_PROVIDER_PRESETS,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
    ProviderIdentity,
)
from memcommit.providers.subscription import QueryProviderError
from memcommit.providers.semantic import connect_operation_provider


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Inspect, select, and verify semantic-provider routing.",
)


def _provider_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SEMANTIC_PROVIDER_IDS:
        raise typer.BadParameter("choose one of: " + ", ".join(SEMANTIC_PROVIDER_IDS))
    return normalized


def _model_label(model: str | None) -> str:
    return model or "Codex managed"


def _resolved_policy_summary(policy: ResolvedProviderPolicy) -> str:
    parts = [policy.provider_id, f"model {_model_label(policy.model)}"]
    if policy.provider_id == CODEX_CHATGPT_PROVIDER:
        parts.append(f"reasoning {policy.reasoning_effort or 'none'}")
        if policy.service_tier is not None:
            parts.append(f"tier {policy.service_tier}")
    parts.append(f"timeout {policy.timeout_seconds:g}s")
    return " · ".join(parts)


def _route_summary(
    route: ProviderRoute,
    *,
    service_tier: str | None = None,
) -> str:
    parts = [route.provider_id, f"model {_model_label(route.model)}"]
    if route.provider_id == CODEX_CHATGPT_PROVIDER:
        parts.append(f"reasoning {route.reasoning_effort or 'none'}")
        if service_tier is not None:
            parts.append(f"tier {service_tier}")
    parts.append(f"timeout {route.timeout_seconds:g}s")
    return " · ".join(parts)


def _render_provider_overview(config: Config) -> None:
    registry = load_profile_registry()
    scope = load_active_provider_scope(machine_config=config, registry=registry)
    typer.echo("PROFILE PROVIDER ROUTES")
    typer.echo(f"profile: {scope.profile.name}")
    typer.echo(
        "mode: " + ("general · editable" if scope.editable else "study · locked")
    )
    typer.echo("contact_status: not_contacted")
    typer.echo(f"policy_version: {POLICY_VERSION}")
    if scope.mode == "STUDY":
        typer.echo(f"study_config: {scope.study_policy_version}")
        typer.echo(f"study_config_digest: {scope.study_policy_digest}")
    typer.echo()

    if scope.mode == "STUDY":
        study = study_provider_config(scope.study_policy_version)
        typer.echo("default:")
        typer.echo(
            f"  {_route_summary(study.default, service_tier=study.service_tier)}"
        )
        typer.echo("operation_routes:")
        width = max(len(operation) for operation in study.operations)
        for operation, route in study.operations.items():
            typer.echo(
                f"  {operation:<{width}}  "
                f"{_route_summary(route, service_tier=study.service_tier)}"
            )
        typer.echo()
        typer.echo("configure: unavailable in a Study Profile")
        typer.echo("verify: mem provider probe [--operation OPERATION]")
        return

    default, _ = resolve_active_provider_policy(
        "semantic_default",
        machine_config=config,
        registry=registry,
    )
    typer.echo("default:")
    typer.echo(f"  {_resolved_policy_summary(default)}")
    typer.echo(f"  source: {default.source.lower()}")
    typer.echo("operation_routes:")
    assert scope.routes is not None
    if scope.routes.operations:
        width = max(len(operation) for operation in scope.routes.operations)
        for operation, route in sorted(scope.routes.operations.items()):
            typer.echo(f"  {operation:<{width}}  {_route_summary(route)}")
    else:
        typer.echo("  none configured")
    typer.echo("other_operations: use default")
    typer.echo()
    typer.echo("configure: mem provider use PROVIDER [--operation OPERATION]")
    typer.echo("reset: mem provider reset [--operation OPERATION]")
    typer.echo("verify: mem provider probe [--operation OPERATION]")


def _report_provider_configuration_error(error: Exception) -> None:
    typer.secho(
        f"Provider configuration error: {error}",
        fg=typer.colors.RED,
        err=True,
    )


@app.callback(invoke_without_command=True)
def provider_group(ctx: typer.Context) -> None:
    """Show active-Profile routes when no explicit action is selected."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        # Bare Provider is deliberately observation-only in every terminal.
        # Editing or contacting a provider requires an explicit subcommand.
        _render_provider_overview(Config())
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


@app.command("use")
def use_provider(
    provider: Annotated[
        str,
        typer.Argument(help="codex_chatgpt, ollama, or openrouter"),
    ],
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Provider model name or slug"),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option("--preset", help="Codex preset; currently: luna-low"),
    ] = None,
    reasoning: Annotated[
        Optional[str],
        typer.Option("--reasoning", help="Codex reasoning effort"),
    ] = None,
    operation: Annotated[
        Optional[str],
        typer.Option("--operation", help="Configure only this semantic operation"),
    ] = None,
    timeout_seconds: Annotated[
        Optional[float],
        typer.Option("--timeout-seconds", min=0.001, help="Provider call timeout"),
    ] = None,
    context_tokens: Annotated[
        Optional[int],
        typer.Option("--context-tokens", min=1, help="Ollama context allocation"),
    ] = None,
    max_output_tokens: Annotated[
        Optional[int],
        typer.Option("--max-output-tokens", min=1, help="Completion token budget"),
    ] = None,
    thinking: Annotated[
        str,
        typer.Option("--thinking", help="Ollama thinking mode: auto, on, or off"),
    ] = "auto",
    zdr: Annotated[
        bool,
        typer.Option(
            "--zdr/--no-zdr",
            help="Require an OpenRouter zero-data-retention route",
        ),
    ] = False,
) -> None:
    """Set a default or operation route for the active ordinary Profile."""
    config = Config()
    try:
        registry = load_profile_registry()
        scope = load_active_provider_scope(
            machine_config=config,
            registry=registry,
        )
        if not scope.editable:
            raise ProfileProviderRoutesError(
                "Provider configuration is fixed for this Study Profile. Switch "
                "to an ordinary Profile to edit provider routes."
            )
        policy_operation = operation or "semantic_default"
        current, _ = resolve_active_provider_policy(
            policy_operation,
            machine_config=config,
            registry=registry,
        )
        selected_provider = _provider_name(provider)
        thinking_mode = thinking.strip().lower()
        if thinking_mode not in {"auto", "on", "off"}:
            raise typer.BadParameter("--thinking must be auto, on, or off")
        selected_preset = preset.strip().lower() if preset is not None else None
        selected_reasoning = (
            reasoning.strip().lower() if reasoning is not None else None
        )
        if (
            selected_preset is not None
            and selected_preset not in CODEX_PROVIDER_PRESETS
        ):
            raise typer.BadParameter(
                "--preset must be one of: " + ", ".join(CODEX_PROVIDER_PRESETS)
            )
        if (
            selected_reasoning is not None
            and selected_reasoning not in CODEX_REASONING_EFFORTS
        ):
            raise typer.BadParameter(
                "--reasoning must be one of: " + ", ".join(CODEX_REASONING_EFFORTS)
            )
        if selected_provider != CODEX_CHATGPT_PROVIDER and (
            selected_preset is not None or selected_reasoning is not None
        ):
            raise typer.BadParameter("--preset and --reasoning apply only to Codex")
        if selected_preset is not None and (model is not None or reasoning is not None):
            raise typer.BadParameter(
                "--preset cannot be combined with --model or --reasoning"
            )

        if selected_preset == CODEX_LUNA_LOW_PRESET:
            selected_model = CODEX_LUNA_MODEL
            selected_reasoning = "low"
        elif selected_provider == CODEX_CHATGPT_PROVIDER:
            selected_model = model
            selected_reasoning = selected_reasoning or "none"
        else:
            selected_model = model
            if selected_model is None and current.provider_id == selected_provider:
                selected_model = current.model
            if selected_model is None:
                selected_model = config.model_for_provider(selected_provider)
        if selected_provider != CODEX_CHATGPT_PROVIDER and not selected_model:
            raise typer.BadParameter("--model is required for this provider")

        route = ProviderRoute(
            provider_id=selected_provider,
            model=selected_model,
            reasoning_effort=selected_reasoning,
            timeout_seconds=(
                timeout_seconds
                if timeout_seconds is not None
                else current.timeout_seconds
            ),
        )
        profile, _routes = set_active_profile_route(
            route,
            operation=operation,
            registry=registry,
        )

        # Endpoint/auth-adjacent transport settings remain machine-local. They
        # are deliberately separate from the Profile's provider identity route.
        values: dict[str, object] = {}
        if selected_provider == OLLAMA_PROVIDER:
            values["llm_model"] = selected_model
            values["semantic_thinking"] = {
                "auto": "auto",
                "on": "true",
                "off": "false",
            }[thinking_mode]
        if selected_provider == OPENROUTER_PROVIDER:
            values["openrouter_zdr"] = str(zdr).lower()
        if context_tokens is not None:
            values["semantic_context_tokens"] = str(context_tokens)
        if max_output_tokens is not None:
            values["semantic_max_output_tokens"] = str(max_output_tokens)
        if values:
            config.update(values)

        target = f"operation {operation}" if operation is not None else "default"
        typer.echo(f"Profile provider route: {profile.name} · {target}")
        typer.echo(f"  {_route_summary(route)}")
        if selected_preset:
            typer.echo(f"  preset expanded: {selected_preset}")
        if values:
            typer.echo("Machine transport settings were updated separately.")
        verify = "mem provider probe"
        if operation is not None:
            verify += f" --operation {operation}"
        typer.echo(f"Verify with '{verify}'.")
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


@app.command("reset")
def reset_provider(
    operation: Annotated[
        Optional[str],
        typer.Option("--operation", help="Remove only this operation route"),
    ] = None,
) -> None:
    """Return one active-Profile route to its inherited value."""
    try:
        registry = load_profile_registry()
        profile, _routes = reset_active_profile_route(
            operation,
            registry=registry,
        )
        target = f"operation {operation}" if operation is not None else "default"
        typer.echo(f"Profile provider route reset: {profile.name} · {target}")
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


def _render_transport_status(config: Config, provider: str) -> None:
    typer.echo(f"max_output_tokens: {config.semantic_max_output_tokens()}")
    if provider == OLLAMA_PROVIDER:
        typer.echo(f"endpoint: {config.ollama_base_url()}")
        typer.echo(f"context_tokens: {config.semantic_context_tokens()}")
        thinking = config.semantic_thinking()
        typer.echo(
            "thinking: " + ("auto" if thinking is None else str(thinking).lower())
        )
    elif provider == OPENROUTER_PROVIDER:
        typer.echo(
            "api_key: "
            + ("available" if os.environ.get("OPENROUTER_API_KEY") else "missing")
        )
        typer.echo(f"zdr: {str(config.openrouter_zdr()).lower()}")
        typer.echo("fallbacks: disabled")


@app.command("status")
def provider_status(
    operation: Annotated[
        Optional[str],
        typer.Option("--operation", help="Resolve one semantic operation"),
    ] = None,
) -> None:
    """Show one effective active-Profile route, without provider contact."""
    config = Config()
    try:
        policy_operation = operation or "semantic_default"
        resolved, scope = resolve_active_provider_policy(
            policy_operation,
            machine_config=config,
        )
        typer.echo(
            "scope: "
            + ("effective_operation" if operation is not None else "profile_default")
        )
        typer.echo(f"profile: {scope.profile.name}")
        typer.echo(f"profile_mode: {scope.mode.lower()}")
        if operation is not None:
            typer.echo(f"operation: {resolved.operation}")
        typer.echo(f"route_source: {resolved.source.lower()}")
        typer.echo(f"policy_version: {POLICY_VERSION}")
        if scope.study_policy_version is not None:
            typer.echo(f"study_config: {scope.study_policy_version}")
            typer.echo(f"study_config_digest: {scope.study_policy_digest}")
        typer.echo(f"route_digest: {resolved.digest}")
        typer.echo(f"provider: {resolved.provider_id}")
        typer.echo(f"model: {_model_label(resolved.model)}")
        typer.echo(f"timeout_seconds: {resolved.timeout_seconds:g}")
        if resolved.provider_id == CODEX_CHATGPT_PROVIDER:
            typer.echo(f"reasoning: {resolved.reasoning_effort or 'none'}")
            typer.echo(f"service_tier: {resolved.service_tier or 'standard'}")
        _render_transport_status(config, resolved.provider_id)
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


@app.command("probe")
def provider_probe(
    operation: Annotated[
        Optional[str],
        typer.Option("--operation", help="Probe one effective operation route"),
    ] = None,
) -> None:
    """Run one strict-schema completion on the active Profile's route."""
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["READY"]},
            "echo": {"type": "string", "enum": ["memcommit-provider-probe"]},
        },
        "required": ["status", "echo"],
        "additionalProperties": False,
    }
    try:
        policy_operation = operation or "semantic_default"
        registry = load_profile_registry()
        scope = load_active_provider_scope(registry=registry)
        with CommandProgress(
            "PROVIDER PROBE",
            "connecting provider",
            total=2,
        ) as progress:
            provider, policy = connect_operation_provider(
                policy_operation,
                profile_registry=registry,
            )
            progress.update("checking completion", step=2)
            raw = provider.complete(
                "Return the requested synthetic provider probe result.",
                operation="provider probe",
                output_schema=schema,
            )
        parsed = json.loads(raw)
        if parsed != {"status": "READY", "echo": "memcommit-provider-probe"}:
            raise QueryProviderError(
                "The provider probe did not satisfy the exact output contract."
            )
        identity = getattr(provider, "identity", None)
        label = (
            identity.display_name()
            if isinstance(identity, ProviderIdentity)
            else f"{CODEX_CHATGPT_PROVIDER}:recommended"
        )
        typer.echo(f"Provider ready: {label}")
        typer.echo(f"profile: {scope.profile.name}")
        typer.echo(f"profile_mode: {scope.mode.lower()}")
        typer.echo(
            "probe_scope: "
            + (f"operation {operation}" if operation is not None else "profile_default")
        )
        typer.echo(f"route_source: {policy.source.lower()}")
        typer.echo(f"route_digest: {policy.digest}")
    except (
        QueryProviderError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        typer.secho(f"Provider probe failed: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
