"""Command-owned catalog for saved Memory quality Audit sessions."""

from __future__ import annotations

from datetime import datetime

from memcommit.adapters.console.terminal.components.operation_launcher.session import SessionPickerEntry
from memcommit.application.capabilities.reviewing.quality.audit import QualityAuditSession
from memcommit.application.capabilities.reviewing.quality.audit_store import QualityAuditStore


def _timestamp(session: QualityAuditSession, sessions: QualityAuditStore) -> float:
    try:
        created = datetime.fromisoformat(session.created_at).timestamp()
    except (TypeError, ValueError) as error:
        raise ValueError("Saved Audit has an invalid creation time.") from error
    path = sessions.path(session.uid)
    try:
        if path.is_file() and not path.is_symlink():
            return max(created, path.stat().st_mtime)
    except FileNotFoundError:
        pass
    return created


def audit_session_entries(
    sessions: QualityAuditStore,
) -> tuple[SessionPickerEntry, ...]:
    """Project every validated completed Audit into the common picker."""

    entries: list[SessionPickerEntry] = []
    for session in sessions.list():
        counts = {check.kind: len(check.report.findings) for check in session.checks}
        check_total = 4 if session.conformance is not None else 3
        conformance_suffix = (
            f" · CONF {session.conformance.issue_count}"
            if session.conformance is not None
            else ""
        )
        entries.append(
            SessionPickerEntry(
                kind="audit",
                key=session.uid,
                title=session.source.context_name,
                status=(
                    f"{check_total}/{check_total} CHECKS · {session.answered_count}/"
                    f"{session.finding_count} ANSWERED"
                ),
                subtitle=(
                    f"DUP {counts['duplicates']} · AMB {counts['ambiguities']} · "
                    f"CONFLICT {counts['conflicts']}{conformance_suffix}"
                ),
                group=session.source.context_name,
                sort_timestamp=_timestamp(session, sessions),
                detail="\n".join(
                    (
                        f"Audit {session.uid}",
                        f"Created {session.created_at}",
                        f"Source {session.source.context_name}",
                        f"Direct Memories {len(session.source.memories)}",
                        (
                            "Duplicate, Ambiguity, Conflict"
                            + (", and Conformance" if session.conformance is not None else "")
                            + " checks: FINISHED"
                        ),
                        "Source: UNCHANGED BY AUDIT",
                    )
                ),
                reopen_argv=(
                    "mem",
                    "review",
                    "audit",
                    "--session",
                    session.uid,
                ),
            )
        )
    return tuple(
        sorted(
            entries,
            key=lambda entry: (
                -entry.sort_timestamp,
                entry.title.casefold(),
                entry.key,
            ),
        )
    )
