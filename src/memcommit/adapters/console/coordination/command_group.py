"""Conservative command-name routing for coordinated ``mem`` groups."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from difflib import get_close_matches
from typing import Any, Final

from typer.core import TyperGroup


# These aliases change only grammatical number. They remain input spellings of
# the plural canonical operations, never independent Help or receipt identities.
EXPLICIT_COMMAND_NAME_ALIASES: Final[Mapping[str, str]] = {
    "find-redundancy": "find-redundancies",
    "find-duplicate": "find-duplicates",
    "find-ambiguity": "find-ambiguities",
    "find-conflict": "find-conflicts",
}


def command_name_alias_targets(
    command_names: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    """Return accepted non-canonical spellings and their canonical targets.

    A hyphen may be omitted, but it may not be replaced by another separator.
    Keeping this rule directional avoids accepting arbitrary new punctuation in
    a command token while covering the observed ``initstudy`` input pattern.
    """

    names = tuple(command_names)
    available = set(names)
    targets: defaultdict[str, set[str]] = defaultdict(set)
    for canonical in names:
        if "-" in canonical:
            targets[canonical.replace("-", "")].add(canonical)
    for alias, canonical in EXPLICIT_COMMAND_NAME_ALIASES.items():
        if canonical not in available:
            continue
        targets[alias].add(canonical)
        if "-" in alias:
            targets[alias.replace("-", "")].add(canonical)
    return {
        alias: tuple(sorted(canonical_names))
        for alias, canonical_names in targets.items()
        if alias not in available
    }


def resolve_canonical_command_name(
    candidate: str,
    command_names: Iterable[str],
) -> str | None:
    """Resolve one exact or explicitly tolerated token without fuzzy execution."""

    names = tuple(command_names)
    if candidate in names:
        return candidate
    targets = command_name_alias_targets(names).get(candidate, ())
    return targets[0] if len(targets) == 1 else None


def command_name_alias_collisions(
    command_names: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    """Return ambiguous accepted spellings for registration-time or CI audits."""

    return {
        alias: targets
        for alias, targets in command_name_alias_targets(command_names).items()
        if len(targets) > 1
    }


class CanonicalCommandGroup(TyperGroup):
    """Resolve safe aliases while retaining one canonical command identity."""

    def canonical_command_name(self, ctx: Any, candidate: str) -> str | None:
        command = self.get_command(ctx, candidate)
        if command is not None:
            return candidate
        if ctx.token_normalize_func is not None:
            normalized = ctx.token_normalize_func(candidate)
            command = self.get_command(ctx, normalized)
            if command is not None:
                return normalized
        return resolve_canonical_command_name(candidate, self.commands)

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
        spelling_to_canonical = {name: name for name in visible}
        for spelling, targets in command_name_alias_targets(visible).items():
            if len(targets) == 1:
                spelling_to_canonical[spelling] = targets[0]
        matches = get_close_matches(
            candidate,
            tuple(spelling_to_canonical),
            n=5,
            cutoff=0.6,
        )
        suggestions: list[str] = []
        for match in matches:
            canonical = spelling_to_canonical[match]
            if canonical not in suggestions:
                suggestions.append(canonical)
            if len(suggestions) == 3:
                break
        return tuple(suggestions)

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
        if len(suggestions) == 1:
            message += f" Did you mean {suggestions[0]!r}?"
        elif suggestions:
            message += " Did you mean one of: " + ", ".join(
                repr(suggestion) for suggestion in suggestions
            ) + "?"
        ctx.fail(message)
        raise AssertionError("ctx.fail() must terminate command resolution")
