"""Run and persist one durable Memory quality Audit from the console."""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import ExitStack
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.audit.receipt import (
    render_quality_audit_receipt,
)
from memcommit.adapters.console.coordination.context_operand import (
    choose_context_operand,
)
from memcommit.adapters.console.terminal.components.progress import (
    BUSY_INTERVAL_SECONDS,
    CommandProgress,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.capabilities.memory_issue_analysis.model import (
    FindingsError,
    FindingsProvider,
)
from memcommit.application.operations.audit.inputs import AuditRequest
from memcommit.application.operations.audit.model import (
    AuditCheckKind,
    QualityAuditError,
    QualityAuditSession,
)
from memcommit.application.operations.audit.report import audit_check_label
from memcommit.application.operations.audit.repository import AuditRecordRepository
from memcommit.application.operations.audit.runtime import run_audit
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.operations.audit import JsonAuditRecordRepository
from memcommit.persistence.store import ConcurrentContextUpdateError, MemoryStore
from memcommit.providers.connection import connect_semantic_provider
from memcommit.providers.errors import QueryProviderError


def _parse_check_list(values: list[str] | None) -> frozenset[AuditCheckKind] | None:
    """Translate comma-separated console values into the application selection."""

    if values is None:
        return None
    selected: set[AuditCheckKind] = set()
    for value in values:
        for name in value.split(","):
            name = name.strip()
            if not name:
                raise QualityAuditError(
                    "--check requires a nonempty comma-separated list."
                )
            try:
                selected.add(AuditCheckKind(name))
            except ValueError as error:
                choices = ", ".join(kind.value for kind in AuditCheckKind)
                raise QualityAuditError(
                    f"Unknown --check value '{name}'. Choose from: {choices}."
                ) from error
    if not selected:
        raise QualityAuditError("--check requires at least one check.")
    return frozenset(selected)


def _check_stage(kind: AuditCheckKind) -> str:
    return f"finding {audit_check_label(kind.value).casefold()}"


def _run_audit_with_progress(
    request: AuditRequest,
    *,
    store: MemoryStore,
    repository: AuditRecordRepository,
    provider_factory: Callable[[], FindingsProvider],
    interactive: bool | None = None,
    interval: float = BUSY_INTERVAL_SECONDS,
) -> QualityAuditSession:
    """Display the stages reported by Application on one transient line."""

    enabled = (
        sys.stdin.isatty() and sys.stdout.isatty()
        if interactive is None
        else interactive
    )
    with ExitStack() as stack:
        progress: CommandProgress | None = None

        def show_progress(kind: AuditCheckKind, step: int, total: int) -> None:
            nonlocal progress
            if progress is None:
                progress = stack.enter_context(
                    CommandProgress(
                        "AUDIT",
                        _check_stage(kind),
                        total=total,
                        step=step,
                        enabled=True if enabled else None,
                        interval=interval,
                    )
                )
            else:
                progress.update(_check_stage(kind), step=step)

        return run_audit(
            request,
            store=store,
            provider_factory=provider_factory,
            repository=repository,
            on_progress=show_progress,
        )


def cmd(
    context_operand: Annotated[
        Optional[str],
        typer.Argument(
            metavar="CONTEXT",
            help="Exact readable Context to audit (defaults to current)",
        ),
    ] = None,
    context_name: Annotated[
        Optional[str],
        typer.Option(
            "--context",
            "-c",
            help="Exact readable Context to audit (defaults to current)",
        ),
    ] = None,
    check: Annotated[
        Optional[list[str]],
        typer.Option(
            "--check",
            metavar="CHECK[,CHECK...]",
            show_default=False,
            help=(
                "Run only these checks: dup, dun, ambiguities, conflicts. "
                "Comma-separated; may be repeated. "
                "Omit to use the standard check list."
            ),
        ),
    ] = None,
) -> None:
    """Run the standard or explicitly selected Audit checks."""

    try:
        context_name = choose_context_operand(
            context_operand,
            option=context_name,
        )
        checks = _parse_check_list(check or None)
        request = AuditRequest(
            context_name=context_name,
            checks=checks,
        )
    except ValueError as error:
        typer.secho(
            "Audit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2)
    try:
        store = MemoryStore(create=False)
        session = _run_audit_with_progress(
            request,
            store=store,
            repository=JsonAuditRecordRepository(store),
            provider_factory=connect_semantic_provider,
        )
    except (
        ConcurrentContextUpdateError,
        FileNotFoundError,
        FindingsError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QualityAuditError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Audit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    render_quality_audit_receipt(session)
