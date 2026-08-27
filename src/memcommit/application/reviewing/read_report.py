"""Operation-neutral identity for read-only report executions and Recents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ReadReportOperation = Literal[
    "summarize",
    "trace",
    "rationale",
    "dedun",
    "find-redundancies",
    "find-duplicates",
    "find-ambiguities",
    "find-conflicts",
]
ReadReportSelectionMode = Literal["SINGLE", "MULTIPLE"]
ReadReportRange = Literal["DIRECT", "RECURSIVE"]

READ_REPORT_OPERATIONS = frozenset(
    {
        "summarize",
        "trace",
        "rationale",
        "dedun",
        "find-redundancies",
        "find-duplicates",
        "find-ambiguities",
        "find-conflicts",
    }
)


class ReadReportError(ValueError):
    """A read-report identity or recent receipt is invalid."""


def _names(values: object, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(values, tuple) or any(
        not isinstance(value, str)
        or not value
        or any(character in value for character in "\r\n")
        for value in values
    ):
        raise ReadReportError(f"Read Report {label} are invalid.")
    if not allow_empty and not values:
        raise ReadReportError(f"Read Report {label} cannot be empty.")
    if len(set(values)) != len(values):
        raise ReadReportError(f"Read Report {label} repeat a name.")
    return values


@dataclass(frozen=True)
class ReadReportTarget:
    """Content-free locator/range identity sufficient to rerun one report."""

    operation: ReadReportOperation
    context_names: tuple[str, ...]
    target_names: tuple[str, ...]
    selection_mode: ReadReportSelectionMode
    ranges: tuple[ReadReportRange, ...]
    profile_selected: bool = False
    memory_uid: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in READ_REPORT_OPERATIONS:
            raise ReadReportError("Read Report operation is invalid.")
        contexts = _names(self.context_names, label="Context names")
        targets = _names(
            self.target_names,
            label="target names",
            allow_empty=self.profile_selected,
        )
        if not set(targets) <= set(contexts):
            raise ReadReportError("Read Report targets are outside its Context set.")
        if self.profile_selected and targets:
            # PROFILE is the virtual all-readable target. Retaining ordinary
            # roots beside it would make replay semantics depend on which of
            # two contradictory target identities a caller happened to use.
            raise ReadReportError(
                "A Profile Read Report cannot retain ordinary target names."
            )
        if self.selection_mode not in {"SINGLE", "MULTIPLE"}:
            raise ReadReportError("Read Report selection mode is invalid.")
        if (
            self.selection_mode == "SINGLE"
            and not self.profile_selected
            and len(targets) != 1
        ):
            raise ReadReportError("A single Read Report requires one target.")
        if type(self.profile_selected) is not bool:
            raise ReadReportError("Read Report Profile selection is invalid.")
        if (
            not isinstance(self.ranges, tuple)
            or not self.ranges
            or len(set(self.ranges)) != len(self.ranges)
            or any(value not in {"DIRECT", "RECURSIVE"} for value in self.ranges)
            or self.ranges not in {("DIRECT",), ("RECURSIVE",), ("DIRECT", "RECURSIVE")}
        ):
            raise ReadReportError("Read Report ranges are invalid.")
        if self.memory_uid is not None and (
            not isinstance(self.memory_uid, str)
            or not self.memory_uid
            or any(character in self.memory_uid for character in "\r\n")
        ):
            raise ReadReportError("Read Report Memory UID is invalid.")
        if self.operation in {"trace", "rationale"}:
            if self.memory_uid is None or len(contexts) != 1:
                raise ReadReportError(
                    "Memory reports require one Context and one Memory UID."
                )
        elif self.memory_uid is not None:
            raise ReadReportError(
                "Context reports cannot retain a Memory UID in Recents."
            )
        if self.operation == "trace" and self.ranges != ("DIRECT",):
            raise ReadReportError("Trace has an exact direct report range.")

    @property
    def include_descendants(self) -> bool:
        """Return the single range as a boolean where one range is required."""

        if len(self.ranges) != 1:
            raise ReadReportError("This Read Report retains both ranges.")
        return self.ranges[0] == "RECURSIVE"

    def to_metadata(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "context_names": list(self.context_names),
            "target_names": list(self.target_names),
            "selection_mode": self.selection_mode,
            "ranges": list(self.ranges),
            "profile_selected": self.profile_selected,
            **({"memory_uid": self.memory_uid} if self.memory_uid is not None else {}),
        }

    @classmethod
    def from_metadata(cls, value: object) -> "ReadReportTarget":
        if not isinstance(value, dict):
            raise ReadReportError("Read Report metadata is invalid.")
        allowed = {
            "operation",
            "context_names",
            "target_names",
            "selection_mode",
            "ranges",
            "profile_selected",
            "memory_uid",
        }
        if set(value) - allowed or not {
            "operation",
            "context_names",
            "target_names",
            "selection_mode",
            "ranges",
            "profile_selected",
        } <= set(value):
            raise ReadReportError("Read Report metadata shape is invalid.")
        try:
            return cls(
                operation=value["operation"],  # type: ignore[arg-type]
                context_names=tuple(value["context_names"]),  # type: ignore[arg-type]
                target_names=tuple(value["target_names"]),  # type: ignore[arg-type]
                selection_mode=value["selection_mode"],  # type: ignore[arg-type]
                ranges=tuple(value["ranges"]),  # type: ignore[arg-type]
                profile_selected=value["profile_selected"],  # type: ignore[arg-type]
                memory_uid=value.get("memory_uid"),  # type: ignore[arg-type]
            )
        except (TypeError, KeyError) as error:
            raise ReadReportError("Read Report metadata values are invalid.") from error


@dataclass(frozen=True)
class ReadReportRecent:
    """One completed content-free attempt projected into Recents."""

    attempt_uid: str
    target: ReadReportTarget
    started_at: str

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_uid, str) or not self.attempt_uid:
            raise ReadReportError("Read Report recent UID is invalid.")
        if not isinstance(self.target, ReadReportTarget):
            raise ReadReportError("Read Report recent target is invalid.")
        if not isinstance(self.started_at, str) or not self.started_at:
            raise ReadReportError("Read Report recent time is invalid.")


__all__ = [
    "READ_REPORT_OPERATIONS",
    "ReadReportError",
    "ReadReportOperation",
    "ReadReportRange",
    "ReadReportRecent",
    "ReadReportSelectionMode",
    "ReadReportTarget",
]
