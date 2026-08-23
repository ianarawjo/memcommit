"""Select and probe the provider used by semantic commands."""
from __future__ import annotations

import json
import os
from typing import Annotated, Optional

import typer

from memcommit.commands.command_group import CanonicalCommandGroup
from memcommit.commands.command_progress import CommandProgress
from memcommit.config import Config
from memcommit.provider_types import (
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
from memcommit.query_provider import QueryProviderError
from memcommit.semantic_provider import connect_operation_provider
from memcommit.infrastructure.providers.policy import (
    OPERATION_PROVIDER_POLICIES,
    POLICY_VERSION,
    OperationProviderPolicy,
    ResolvedProviderPolicy,
    operation_provider_policy,
    resolve_operation_provider_policy,
)


app = typer.Typer(
    cls=CanonicalCommandGroup,
    invoke_without_command=True,
    no_args_is_help=False,
    help="Inspect, select, and verify semantic-provider routing.",
)


def _provider_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SEMANTIC_PROVIDER_IDS:
        raise typer.BadParameter(
            "choose one of: " + ", ".join(SEMANTIC_PROVIDER_IDS)
        )
    return normalized


def _model_label(model: str | None) -> str:
    return model or "Codex current recommended selection"


def _resolved_policy_summary(policy: ResolvedProviderPolicy) -> str:
    parts = [policy.provider_id, f"model {_model_label(policy.model)}"]
    if policy.provider_id == CODEX_CHATGPT_PROVIDER:
        parts.append(f"reasoning {policy.reasoning_effort or 'none'}")
    parts.append(f"timeout {policy.timeout_seconds:g}s")
    return " · ".join(parts)


def _authored_rule_summary(policy: OperationProviderPolicy) -> str:
    pins_identity = any(
        value is not None
        for value in (
            policy.provider_id,
            policy.model,
            policy.reasoning_effort,
        )
    )
    if pins_identity:
        return "pinned identity"
    if policy.timeout_floor_seconds is not None:
        return (
            "inherits global identity · timeout floor "
            f"{policy.timeout_floor_seconds:g}s"
        )
    return "inherits global default"


def _render_provider_overview(config: Config) -> None:
    default = resolve_operation_provider_policy("semantic_default", config=config)
    typer.echo("SEMANTIC PROVIDER ROUTING")
    typer.echo("config_scope: global · all Profiles")
    typer.echo("contact_status: not_contacted")
    typer.echo(f"policy_version: {POLICY_VERSION}")
    typer.echo()
    typer.echo("global_default:")
    typer.echo(f"  {_resolved_policy_summary(default)}")
    typer.echo()
    typer.echo("authored_operation_policies:")
    width = max(len(name) for name in OPERATION_PROVIDER_POLICIES)
    for operation, authored in OPERATION_PROVIDER_POLICIES.items():
        resolved = resolve_operation_provider_policy(operation, config=config)
        typer.echo(
            f"  {operation:<{width}}  {_resolved_policy_summary(resolved)}"
        )
        typer.echo(f"  {'':<{width}}  rule: {_authored_rule_summary(authored)}")
    typer.echo()
    typer.echo("other_operations: inherit global_default")
    typer.echo("inspect: mem provider status --operation OPERATION")
    typer.echo("verify: mem provider probe [--operation OPERATION]")


def _report_provider_configuration_error(error: Exception) -> None:
    typer.secho(
        f"Provider configuration error: {error}",
        fg=typer.colors.RED,
        err=True,
    )


@app.callback(invoke_without_command=True)
def provider_group(ctx: typer.Context) -> None:
    """Show routing when no explicit provider action is selected."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        _render_provider_overview(Config())
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


@app.command("use")
def use_provider(
    provider: Annotated[str, typer.Argument(help="codex_chatgpt, ollama, or openrouter")],
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Provider model name or slug"),
    ] = None,
    preset: Annotated[
        Optional[str],
        typer.Option(
            "--preset",
            help="Codex preset; currently: luna-low",
        ),
    ] = None,
    reasoning: Annotated[
        Optional[str],
        typer.Option(
            "--reasoning",
            help="Codex reasoning effort for an explicit model",
        ),
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
        typer.Option(
            "--thinking",
            help="Ollama thinking mode: auto, on, or off",
        ),
    ] = "auto",
    zdr: Annotated[
        bool,
        typer.Option(
            "--zdr/--no-zdr",
            help="Require an OpenRouter zero-data-retention route",
        ),
    ] = False,
) -> None:
    """Set the global default used by operations without an authored override."""
    provider = _provider_name(provider)
    thinking_mode = thinking.strip().lower()
    if thinking_mode not in {"auto", "on", "off"}:
        raise typer.BadParameter("--thinking must be auto, on, or off")
    config = Config()
    selected_preset = preset.strip().lower() if preset is not None else None
    selected_reasoning = (
        reasoning.strip().lower() if reasoning is not None else None
    )
    if selected_preset is not None and selected_preset not in CODEX_PROVIDER_PRESETS:
        raise typer.BadParameter(
            "--preset must be one of: " + ", ".join(CODEX_PROVIDER_PRESETS)
        )
    if selected_reasoning is not None and selected_reasoning not in CODEX_REASONING_EFFORTS:
        raise typer.BadParameter(
            "--reasoning must be one of: " + ", ".join(CODEX_REASONING_EFFORTS)
        )
    if provider != CODEX_CHATGPT_PROVIDER and (
        selected_preset is not None or selected_reasoning is not None
    ):
        raise typer.BadParameter("--preset and --reasoning apply only to Codex")
    if selected_preset is not None and (model is not None or reasoning is not None):
        raise typer.BadParameter(
            "--preset cannot be combined with --model or --reasoning"
        )
    if (
        provider == CODEX_CHATGPT_PROVIDER
        and selected_reasoning is not None
        and model is None
    ):
        raise typer.BadParameter("--reasoning requires --model or --preset")

    if selected_preset == CODEX_LUNA_LOW_PRESET:
        selected_model = CODEX_LUNA_MODEL
        selected_reasoning = "low"
    elif provider == CODEX_CHATGPT_PROVIDER:
        selected_model = model
    else:
        selected_model = model or config.model_for_provider(provider)
    if provider != CODEX_CHATGPT_PROVIDER and not selected_model:
        raise typer.BadParameter("--model is required for this provider")
    values: dict[str, object] = {"semantic_provider": provider}
    if provider == CODEX_CHATGPT_PROVIDER:
        # Empty strings intentionally restore the managed Codex selection when
        # the bare command is used; stale provider settings must not survive a
        # request to return to the original behavior.
        values["semantic_model"] = selected_model or ""
        values[f"{provider}_model"] = selected_model or ""
        values[f"{provider}_reasoning_effort"] = selected_reasoning or ""
        values[f"{provider}_preset"] = selected_preset or ""
    else:
        values["semantic_model"] = selected_model
        values[f"{provider}_model"] = selected_model
    if provider == OLLAMA_PROVIDER:
        # Keep the two legacy Ollama-only commands on the same local model
        # during the provider-independent rollout.
        values["llm_model"] = selected_model
        values["semantic_thinking"] = {
            "auto": "auto",
            "on": "true",
            "off": "false",
        }[thinking_mode]
    if provider == OPENROUTER_PROVIDER:
        values["openrouter_zdr"] = str(zdr).lower()
    if context_tokens is not None:
        values["semantic_context_tokens"] = str(context_tokens)
    if max_output_tokens is not None:
        values["semantic_max_output_tokens"] = str(max_output_tokens)
    config.update(values)
    suffix = f" · model {selected_model}" if selected_model else ""
    if selected_reasoning:
        suffix += f" · reasoning {selected_reasoning}"
    if selected_preset:
        suffix += f" · preset {selected_preset}"
    typer.echo(f"Global semantic default: {provider}{suffix}")
    typer.echo("Scope: all Profiles; operation-specific policies are unchanged.")
    typer.echo(
        "Verify with 'mem provider probe' or add '--operation OPERATION' "
        "for an authored route."
    )


@app.command("status")
def provider_status(
    operation: Annotated[
        Optional[str],
        typer.Option(
            "--operation",
            help="Resolve the effective policy for one provider operation",
        ),
    ] = None,
    study: Annotated[
        bool,
        typer.Option(
            "--study",
            help="Resolve the participant-Study policy for the operation",
        ),
    ] = False,
) -> None:
    """Show global defaults or one effective operation policy, without contact."""
    config = Config()
    try:
        if study and operation is None:
            raise typer.BadParameter("--study requires --operation")
        policy_operation = operation or "semantic_default"
        resolved = resolve_operation_provider_policy(
            policy_operation,
            config=config,
            mode="STUDY_PARTICIPANT" if study else "PRODUCTION",
        )
        provider = resolved.provider_id
        model = resolved.model
        typer.echo(
            "scope: "
            + ("effective_operation" if operation is not None else "global_default")
        )
        typer.echo("profile_scope: all_profiles")
        if operation is not None:
            typer.echo(f"operation: {resolved.operation}")
        typer.echo(f"policy_mode: {resolved.mode.lower()}")
        typer.echo(f"policy_source: {resolved.source.lower()}")
        typer.echo(f"policy_version: {POLICY_VERSION}")
        typer.echo(f"policy_digest: {resolved.digest}")
        typer.echo(f"provider: {provider}")
        typer.echo(f"model: {_model_label(model)}")
        typer.echo(f"timeout_seconds: {resolved.timeout_seconds:g}")
        typer.echo(f"max_output_tokens: {config.semantic_max_output_tokens()}")
        if provider == CODEX_CHATGPT_PROVIDER:
            typer.echo(f"reasoning: {resolved.reasoning_effort or 'none'}")
            preset = config.codex_preset()
            authored = operation_provider_policy(policy_operation)
            inherits_identity = all(
                value is None
                for value in (
                    authored.provider_id,
                    authored.model,
                    authored.reasoning_effort,
                )
            )
            if (
                preset
                and inherits_identity
                and config.model_for_provider(CODEX_CHATGPT_PROVIDER) == model
                and (config.codex_reasoning_effort() or "none")
                == resolved.reasoning_effort
            ):
                typer.echo(f"preset: {preset}")
        elif provider == OLLAMA_PROVIDER:
            typer.echo(f"endpoint: {config.ollama_base_url()}")
            typer.echo(f"context_tokens: {config.semantic_context_tokens()}")
            thinking = config.semantic_thinking()
            typer.echo(
                "thinking: "
                + ("auto" if thinking is None else str(thinking).lower())
            )
        elif provider == OPENROUTER_PROVIDER:
            typer.echo(
                "api_key: "
                + ("available" if os.environ.get("OPENROUTER_API_KEY") else "missing")
            )
            typer.echo(f"zdr: {str(config.openrouter_zdr()).lower()}")
            typer.echo("fallbacks: disabled")
    except (RuntimeError, ValueError) as error:
        _report_provider_configuration_error(error)
        raise typer.Exit(1)


@app.command("probe")
def provider_probe(
    operation: Annotated[
        Optional[str],
        typer.Option(
            "--operation",
            help="Probe the effective policy for one provider operation",
        ),
    ] = None,
) -> None:
    """Probe the global default or one operation's effective provider policy."""
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
        with CommandProgress(
            "PROVIDER PROBE",
            "connecting provider",
            total=2,
        ) as progress:
            policy_operation = operation or "semantic_default"
            provider, policy = connect_operation_provider(policy_operation)
            progress.update("checking completion", step=2)
            raw = provider.complete(
                "Return the requested synthetic provider probe result.",
                operation="provider probe",
                output_schema=schema,
            )
        parsed = json.loads(raw)
        if parsed != {
            "status": "READY",
            "echo": "memcommit-provider-probe",
        }:
            raise QueryProviderError(
                "The provider probe did not satisfy the exact output contract."
            )
        identity = getattr(provider, "identity", None)
        if isinstance(identity, ProviderIdentity):
            label = identity.display_name()
        else:
            label = f"{CODEX_CHATGPT_PROVIDER}:recommended"
        typer.echo(f"Provider ready: {label}")
        typer.echo(
            "probe_scope: "
            + (f"operation {operation}" if operation is not None else "global_default")
        )
        typer.echo(f"policy_source: {policy.source.lower()}")
        typer.echo(f"policy_digest: {policy.digest}")
    except (QueryProviderError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        typer.secho(f"Provider probe failed: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
