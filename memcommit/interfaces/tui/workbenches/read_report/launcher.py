"""Content-free recent launcher shared by read-only report operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.interfaces.tui.components.operation_launcher import (
    LauncherAction,
    LauncherActionSelection,
    LauncherEntry,
    LauncherEntrySelection,
    LauncherOrientation,
    OperationLauncherSpec,
    run_operation_launcher,
)
from memcommit.read_report import (
    ReadReportError,
    ReadReportOperation,
    ReadReportRecent,
    ReadReportTarget,
)


@dataclass(frozen=True)
class ReadReportSelectTarget:
    """Request the operation-owned target selector instead of a recent run."""


def _operation_label(operation: ReadReportOperation) -> str:
    return operation.replace("-", " ").upper()


def _range_label(target: ReadReportTarget) -> str:
    if target.ranges == ("DIRECT", "RECURSIVE"):
        return "DIRECT + RECURSIVE"
    return target.ranges[0]


def _route_label(target: ReadReportTarget) -> str:
    if target.profile_selected:
        return "ALL READABLE CONTEXTS"
    if len(target.target_names) == 1:
        return target.target_names[0]
    return f"{len(target.target_names)} TARGET CONTEXTS"


def _entry(recent: ReadReportRecent) -> LauncherEntry:
    try:
        timestamp = datetime.fromisoformat(recent.started_at).timestamp()
    except ValueError as error:
        raise ReadReportError("Recent Read Report time is invalid.") from error
    target = recent.target
    operation = _operation_label(target.operation)
    memory = (
        f" · Memory [{target.memory_uid[:8]}]"
        if target.memory_uid is not None
        else ""
    )
    return LauncherEntry(
        kind=target.operation,
        key=recent.attempt_uid,
        title=_route_label(target),
        status="COMPLETED",
        subtitle=f"{operation} · {_range_label(target)}{memory}",
        group=("PROFILE" if target.profile_selected else target.context_names[0]),
        sort_timestamp=timestamp,
        detail=(
            f"{operation} report\n"
            f"Targets {', '.join(target.target_names) if target.target_names else 'ALL READABLE CONTEXTS'}\n"
            f"Effective Contexts {len(target.context_names)}\n"
            f"Range {_range_label(target)}\n"
            + (
                f"Memory UID {target.memory_uid}\n"
                if target.memory_uid is not None
                else ""
            )
            + f"Opened {recent.started_at}\n\n"
            "Report and Memory content are not copied into Recents. Opening "
            "this row revalidates the current targets and permissions."
        ),
    )


def choose_read_report_recent(
    recents: tuple[ReadReportRecent, ...],
    *,
    operation: ReadReportOperation,
    orientation: LauncherOrientation | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> ReadReportTarget | ReadReportSelectTarget | None:
    """Choose one recent identity or leave for operation-owned targeting."""

    if any(recent.target.operation != operation for recent in recents):
        raise ReadReportError("Read Report Recents contain another operation.")
    if not recents:
        return ReadReportSelectTarget()
    action = LauncherAction(
        uid="select-target",
        label="SELECT A TARGET",
        description=(
            "Leave Recents and choose a new Context, range, or Memory through "
            "the operation-owned target selector."
        ),
    )
    selection = run_operation_launcher(
        OperationLauncherSpec(
            title=f"MEM {_operation_label(operation)} · RECENTS OR SELECT",
            entries=tuple(_entry(recent) for recent in recents),
            action=action,
            orientation=orientation,
            catalog_label="recent reports",
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if selection is None:
        return None
    if isinstance(selection, LauncherActionSelection):
        if selection.uid != action.uid:
            raise ReadReportError("Read Report launcher returned an unknown action.")
        return ReadReportSelectTarget()
    if not isinstance(selection, LauncherEntrySelection):
        raise ReadReportError("Read Report launcher returned an invalid selection.")
    by_key = {recent.attempt_uid: recent for recent in recents}
    selected = by_key.get(selection.key)
    if (
        selected is None
        or selection.kind != operation
        or selected.target.operation != operation
    ):
        raise ReadReportError("Read Report launcher returned an unknown entry.")
    return selected.target


__all__ = ["ReadReportSelectTarget", "choose_read_report_recent"]
