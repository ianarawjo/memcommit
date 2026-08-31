"""Profile Log application boundary and ownership contracts."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import memcommit.application.operations.log.application as log_application
from memcommit.application.operations.log.application import (
    LogEntry,
    LogRequest,
    LogResult,
    run_log,
)


class _StaticLogSource:
    def __init__(self, result: object) -> None:
        self.result = result
        self.requests: list[LogRequest] = []

    def read(self, request: LogRequest):
        self.requests.append(request)
        return self.result


def test_profile_log_returns_a_frozen_user_operation_timeline() -> None:
    entry = LogEntry(
        uid="attempt-1",
        operation="add",
        started_at="2026-08-30T10:00:00+00:00",
        status="COMPLETED",
        command="mem add one",
        outcome="NO_CHANGE",
    )
    result = LogResult(entries=(entry,))
    source = _StaticLogSource(result)
    request = LogRequest(limit=20, exclude_attempt_uid="current-attempt")

    assert run_log(request, source=source) is result
    assert source.requests == [request]
    assert result.entries[0].operation == "add"


def test_profile_log_rejects_invalid_bounds_and_source_results() -> None:
    with pytest.raises(ValueError, match="between 1 and 200"):
        LogRequest(limit=0)
    with pytest.raises(TypeError, match="invalid result"):
        run_log(LogRequest(), source=_StaticLogSource(object()))


def test_log_application_has_no_console_or_persistence_dependency() -> None:
    path = Path(log_application.__file__)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(name.startswith("memcommit.adapters") for name in imports)
    assert not any(name.startswith("memcommit.persistence") for name in imports)
