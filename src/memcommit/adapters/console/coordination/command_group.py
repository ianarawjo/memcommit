"""Conservative command-name routing for coordinated ``mem`` groups."""

from __future__ import annotations

from typing import Any

from typer.core import TyperGroup

from memcommit.application.capabilities.name_suggestions import (
    canonical_name_suggestions,
    did_you_mean_suffix,
)


class CanonicalCommandGroup(TyperGroup):
    """Resolve registered commands and suggest corrections without executing them."""

    def canonical_command_name(self, ctx: Any, candidate: str) -> str | None:
        command = self.get_command(ctx, candidate)
        if command is not None:
            return candidate
        if ctx.token_normalize_func is not None:
            normalized = ctx.token_normalize_func(candidate)
            command = self.get_command(ctx, normalized)
            if command is not None:
                return normalized
        return None

    def _resolve_known_command(
        self,
        ctx: Any,
        candidate: str,
    ) -> tuple[str, Any] | None:
        canonical = self.canonical_command_name(ctx, candidate)
        if canonical is None:
            return None
        command = self.get_command(ctx, canonical)
        if command is None:  # pragma: no cover - guarded by the resolver
            return None
        return canonical, command

    def _command_suggestions(self, ctx: Any, candidate: str) -> tuple[str, ...]:
        visible = {
            name
            for name in self.commands
            if (command := self.get_command(ctx, name)) is not None
            and not command.hidden
        }
        return canonical_name_suggestions(candidate, {name: name for name in visible})

    def resolve_command(
        self,
        ctx: Any,
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        if not args:
            return super().resolve_command(ctx, args)
        candidate = str(args[0])
        resolved = self._resolve_known_command(ctx, candidate)
        if resolved is not None:
            canonical, command = resolved
            return canonical, command, args[1:]
        if candidate.startswith("-") or ctx.resilient_parsing:
            return super().resolve_command(ctx, args)

        message = f"No such command {candidate!r}."
        suggestions = self._command_suggestions(ctx, candidate)
        message += did_you_mean_suffix(suggestions)
        ctx.fail(message)
        raise AssertionError("ctx.fail() must terminate command resolution")
