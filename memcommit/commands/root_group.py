"""Root Click routing shared by every top-level ``mem`` command."""
from __future__ import annotations

import os
import sys
from typing import Any

try:  # Typer 0.27+ vendors Click; older supported Typer releases do not.
    from typer import _click as click
except ImportError:  # pragma: no cover - compatibility with older Typer
    import click

from memcommit.interfaces.cli.command_group import CanonicalCommandGroup

from memcommit.interfaces.console.errors import render_cli_error
from memcommit.authority.write_protection import (
    WriteProtectionError,
    WriteProtectionRegistryError,
)


class MemCommandGroup(CanonicalCommandGroup):
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
        active_study_actions = None
        command_store_dir = None
        entered_argv: tuple[str, ...] | None = None
        if os.environ.get("MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG") != "1":
            from memcommit.command_attempts import begin_command_attempt
            from memcommit.store import MemoryStore

            # Typer 0.27 keeps the unresolved command token on the private
            # compatibility field, while older Click exposes the public
            # property. Combine it with the unparsed trailing operands before
            # child dispatch so the audit record preserves the complete argv.
            protected = tuple(getattr(ctx, "_protected_args", ())) or tuple(
                getattr(ctx, "protected_args", ())
            )
            trailing = tuple(getattr(ctx, "args", ()))
            entered = (*protected, *trailing)
            if any(not isinstance(argument, str) for argument in entered):
                raise TypeError("Root command argv must contain only strings.")
            entered_argv = tuple(entered)
            operation = "mem"
            if entered and isinstance(entered[0], str):
                operation = self.canonical_command_name(ctx, entered[0]) or "mem"
            command_store_dir = MemoryStore(create=False).store_dir
            active_attempt = begin_command_attempt(
                store_dir=command_store_dir,
                operation=operation,
                stdin_tty=sys.stdin.isatty(),
                stdout_tty=sys.stdout.isatty(),
                command_argv=entered_argv,
            )
        try:
            if active_attempt is not None:
                from memcommit.profile_config import (
                    load_profile_registry,
                    profile_store_dir,
                )
                from memcommit.study_action_log import (
                    begin_study_action_recording,
                )

                registry = load_profile_registry()
                process_profile = next(
                    (
                        profile
                        for profile in registry.profiles
                        if profile_store_dir(profile) == command_store_dir
                    ),
                    None,
                )
                if process_profile is not None:
                    active_study_actions = begin_study_action_recording(
                        profile=process_profile,
                        store_dir=command_store_dir,
                        attempt_uid=active_attempt.record.uid,
                        operation=active_attempt.record.operation,
                        stdin_tty=active_attempt.record.stdin_tty,
                        stdout_tty=active_attempt.record.stdout_tty,
                        command_argv=entered_argv,
                    )
            try:
                if active_study_actions is None:
                    result = super().invoke(ctx)
                else:
                    from memcommit.study_action_log import (
                        study_recording_app_session,
                    )

                    with study_recording_app_session():
                        result = super().invoke(ctx)
            except (WriteProtectionError, WriteProtectionRegistryError) as error:
                # Typer renders ClickException with Rich panel chrome, while
                # command-local failures use one plain error line. Protection
                # is caught here for every writer, so render it here through
                # the same shared surface and exit without a second formatter.
                render_cli_error(error)
                raise click.exceptions.Exit(1) from error
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
                try:
                    if active_study_actions is not None:
                        from memcommit.study_action_log import (
                            finish_study_action_recording,
                        )

                        finish_study_action_recording(
                            active_study_actions,
                            status=status,
                            failure_kind=type(error).__name__,
                            exit_code=exit_code,
                        )
                except BaseException as logging_error:
                    error.add_note(
                        "The Study action ledger also failed to finalize: "
                        f"{logging_error}"
                    )
                finally:
                    try:
                        finish_command_attempt(
                            active_attempt,
                            status=status,
                            failure_kind=type(error).__name__,
                            exit_code=exit_code,
                        )
                    except BaseException as logging_error:
                        error.add_note(
                            "The command-attempt ledger also failed to finalize: "
                            f"{logging_error}"
                        )
            raise
        else:
            if active_attempt is not None:
                from memcommit.command_attempts import finish_command_attempt

                study_error: BaseException | None = None
                try:
                    if active_study_actions is not None:
                        from memcommit.study_action_log import (
                            finish_study_action_recording,
                        )

                        finish_study_action_recording(
                            active_study_actions,
                            status="COMPLETED",
                        )
                except BaseException as error:
                    study_error = error
                if study_error is None:
                    finish_command_attempt(active_attempt, status="COMPLETED")
                else:
                    finish_command_attempt(
                        active_attempt,
                        status="FAILED",
                        failure_kind=type(study_error).__name__,
                    )
                    raise study_error
            return result
