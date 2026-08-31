"""Click routing for the concise ``mem profile NAME`` selection form."""

from __future__ import annotations

from typing import Any

from memcommit.adapters.console.coordination.command_group import CanonicalCommandGroup


class ProfileAliasGroup(CanonicalCommandGroup):
    """Route an unknown command token through the existing ``use`` command.

    Known subcommands keep precedence.  The fallback deliberately performs no
    registry lookup here: ``use`` remains the single validation, locking, and
    mutation boundary for both command spellings.
    """

    def resolve_command(
        self,
        ctx: Any,
        args: list[str],
    ) -> tuple[str | None, Any, list[str]]:
        if args:
            candidate = str(args[0])
            resolved = self._resolve_known_command(ctx, candidate)
            if resolved is not None:
                canonical, command = resolved
                return canonical, command, args[1:]
            if not candidate.startswith("-"):
                use_command = self.get_command(ctx, "use")
                if use_command is not None:
                    # Keep the candidate in argv so ``use`` parses it as NAME.
                    return "use", use_command, args
        return super().resolve_command(ctx, args)
