"""Root Click routing shared by every top-level ``mem`` command."""
from __future__ import annotations

import os
import sys
from typing import Any

try:  # Typer 0.27+ vendors Click; older supported Typer releases do not.
    from typer import _click as click
except ImportError:  # pragma: no cover - compatibility with older Typer
    import click
from typer.core import TyperGroup

from memcommit.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistryError,
)


class MemCommandGroup(TyperGroup):
    """Render store-level protection failures without Python tracebacks.

    Protection is enforced below individual commands, including legacy and
    semantic writers.  Converting only these typed failures at the root keeps
    every mutation path consistent without teaching the persistence layer
    about Click or relying on each command to remember a local catch block.
    """

    def invoke(self, ctx: Any) -> Any:
        # A long interactive command may make several semantic turns. Freeze
        # one provider/model instance for that root invocation, while separate
        # CliRunner or embedded invocations still observe explicit config
        # changes made between commands.
        from memcommit.semantic_provider import reset_semantic_provider_cache

        reset_semantic_provider_cache()
        active_attempt = None
        if os.environ.get("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG") != "1":
            from memcommit.command_attempts import begin_command_attempt
            from memcommit.store import MemoryStore

            # Typer 0.27 keeps the unresolved command token on the private
            # compatibility field, while older Click exposes the public
            # property. Read either without touching later raw operands.
            entered = tuple(getattr(ctx, "_protected_args", ())) or tuple(
                getattr(ctx, "protected_args", ())
            )
            operation = (
                entered[0]
                if entered
                and isinstance(entered[0], str)
                and entered[0] in self.commands
                else "mem"
            )
            active_attempt = begin_command_attempt(
                store_dir=MemoryStore(create=False).store_dir,
                operation=operation,
                stdin_tty=sys.stdin.isatty(),
                stdout_tty=sys.stdout.isatty(),
            )
        try:
            try:
                result = super().invoke(ctx)
            except (WriteProtectionError, WriteProtectionRegistryError) as error:
                raise click.ClickException(str(error)) from error
        except BaseException as error:
            if active_attempt is not None:
                from memcommit.command_attempts import finish_command_attempt

                if isinstance(error, KeyboardInterrupt):
                    status = "INTERRUPTED"
                    exit_code = 130
                else:
                    raw_exit_code = getattr(error, "exit_code", None)
                    if raw_exit_code is None and isinstance(error, SystemExit):
                        raw_exit_code = error.code
                    exit_code = raw_exit_code if isinstance(raw_exit_code, int) else None
                    status = "COMPLETED" if exit_code == 0 else "FAILED"
                finish_command_attempt(
                    active_attempt,
                    status=status,
                    failure_kind=type(error).__name__,
                    exit_code=exit_code,
                )
            raise
        else:
            if active_attempt is not None:
                from memcommit.command_attempts import finish_command_attempt

                finish_command_attempt(active_attempt, status="COMPLETED")
            return result
