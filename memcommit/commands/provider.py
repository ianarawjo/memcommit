"""Select and probe the provider used by semantic commands."""
from __future__ import annotations

import json
import os
from typing import Annotated, Optional

import typer

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
from memcommit.query_provider import QueryProviderError, connect_semantic_provider


app = typer.Typer(no_args_is_help=True, help="Select and verify a semantic provider.")


def _provider_name(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in SEMANTIC_PROVIDER_IDS:
        raise typer.BadParameter(
            "choose one of: " + ", ".join(SEMANTIC_PROVIDER_IDS)
        )
    return normalized


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
    """Make one explicit provider/model selection for future commands."""
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
    typer.echo(f"Semantic provider: {provider}{suffix}")
    typer.echo("Run 'mem provider probe' before using it with durable work.")


@app.command("status")
def provider_status() -> None:
    """Show provider selection without contacting it or exposing credentials."""
    config = Config()
    try:
        provider = config.semantic_provider()
        model = config.semantic_model()
        typer.echo(f"provider: {provider}")
        typer.echo(
            "model: "
            + (
                model
                if model
                else "Codex current recommended selection"
            )
        )
        typer.echo(f"timeout_seconds: {config.semantic_timeout_seconds():g}")
        typer.echo(f"max_output_tokens: {config.semantic_max_output_tokens()}")
        if provider == CODEX_CHATGPT_PROVIDER:
            typer.echo(
                "reasoning: "
                + (config.codex_reasoning_effort() or "Codex/model default")
            )
            preset = config.codex_preset()
            if preset:
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
    except RuntimeError as error:
        typer.secho(f"Provider configuration error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)


@app.command("probe")
def provider_probe() -> None:
    """Run one synthetic strict-schema completion against the selection."""
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
        provider = connect_semantic_provider()
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
    except (QueryProviderError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        typer.secho(f"Provider probe failed: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
