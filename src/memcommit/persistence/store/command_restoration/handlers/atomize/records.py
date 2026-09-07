"""Decode restoration receipts without reading or changing live Store state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Iterable

from ....context_memory.records import _context_name_parts

if TYPE_CHECKING:
    from memcommit.application.capabilities.command_recovery.model import (
        CommandContextChange,
    )


def _record(value: object, fields: set[str], message: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(message)
    return value


def _text(value: object, message: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(message)
    return value


def _digest(value: object, message: str) -> str:
    value = _text(value, message)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(message)
    return value


def _current(value: object, message: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise ValueError(message)
    return value


@dataclass(frozen=True)
class SourceWorkbenchReceipt:
    uid: str
    output_context_name: str
    record_digest: str

    @classmethod
    def from_dict(cls, value: object) -> SourceWorkbenchReceipt | None:
        if value is None:
            return None
        message = "Atomize Source workbench receipt is invalid."
        record = _record(
            value, {"uid", "output_context_name", "record_digest"}, message
        )
        return cls(
            uid=_text(record["uid"], message),
            output_context_name=_text(record["output_context_name"], message),
            record_digest=_digest(record["record_digest"], message),
        )


@dataclass(frozen=True)
class AtomizeCreationReceipt:
    """Restoration-relevant fields from an exact version-1 Save As receipt."""

    source_context_uid: str
    source_context_name: str
    analysis_uid: str
    source_workbench: SourceWorkbenchReceipt | None
    current_before: str | None


def load_creation_receipt(
    entries: Iterable[dict[str, object]], change: CommandContextChange
) -> AtomizeCreationReceipt:
    checkpoint = next(
        (entry for entry in entries if entry.get("uid") == change.checkpoint_uid), None
    )
    args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
    message = "Atomize checkpoint has no valid Save As creation receipt."
    if not isinstance(args, dict) or args.get("context_creation") != {
        "version": 1,
        "context_uid": change.context_uid,
        "context_name": change.context_name,
    }:
        raise ValueError(message)
    receipt = _record(
        args.get("atomize_save_as"),
        {
            "version",
            "source_context",
            "source_frame",
            "source_frame_digest",
            "source_analysis_uid",
            "source_workbench",
            "current_before",
        },
        message,
    )
    if receipt["version"] != 1:
        raise ValueError(message)
    message = "Atomize Save As Source receipt is invalid."
    source = _record(receipt["source_context"], {"uid", "name", "digest"}, message)
    analysis_uid = _text(receipt["source_analysis_uid"], message)
    if args.get("analysis_uid") != analysis_uid:
        raise ValueError("Atomize analyses do not match the restored Save As command.")
    # The Source frame is provenance; restoration never re-executes it. The
    # command unit's frozen after-image remains the result-content authority.
    return AtomizeCreationReceipt(
        source_context_uid=_text(source["uid"], message),
        source_context_name=_text(source["name"], message),
        analysis_uid=analysis_uid,
        source_workbench=SourceWorkbenchReceipt.from_dict(receipt["source_workbench"]),
        current_before=_current(receipt["current_before"], message),
    )


@dataclass(frozen=True)
class AtomizeArchiveManifest:
    unit_uid: str
    context_uid: str
    context_name: str
    checkpoint_uid: str
    analysis_uid: str
    source_context_uid: str
    source_context_name: str
    source_workbench: SourceWorkbenchReceipt | None
    reviewing_workbench_digest: str | None
    terminal_workbench_digest: str | None
    current_before: str | None

    def to_dict(self) -> dict[str, object]:
        return {"version": 1, "command": "atomize", **asdict(self)}

    @classmethod
    def from_dict(cls, value: object) -> AtomizeArchiveManifest:
        message = "Command Context archive manifest is invalid."
        record = _record(
            value, {"version", "command", *cls.__dataclass_fields__}, message
        )
        if record["version"] != 1 or record["command"] != "atomize":
            raise ValueError(message)
        strings = {
            field: _text(record[field], message)
            for field in (
                "unit_uid",
                "context_uid",
                "context_name",
                "checkpoint_uid",
                "analysis_uid",
                "source_context_uid",
                "source_context_name",
            )
        }
        if strings["unit_uid"] != f"checkpoint:{strings['checkpoint_uid']}":
            raise ValueError(message)
        _context_name_parts(strings["context_name"])
        _context_name_parts(strings["source_context_name"])
        workbench = SourceWorkbenchReceipt.from_dict(record["source_workbench"])
        reviewing = record["reviewing_workbench_digest"]
        terminal = record["terminal_workbench_digest"]
        if workbench is None:
            if reviewing is not None or terminal is not None:
                raise ValueError(message)
        else:
            reviewing = _digest(reviewing, message)
            terminal = _digest(terminal, message)
        return cls(
            **strings,
            source_workbench=workbench,
            reviewing_workbench_digest=reviewing,
            terminal_workbench_digest=terminal,
            current_before=_current(record["current_before"], message),
        )
