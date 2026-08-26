"""Replay the exact Task 3 Sever through apply, Undo, and Redo."""

from __future__ import annotations

import json
import sys
import time

from capture_init_study import (
    OUT,
    PROFILE_NAME,
    ROOT,
    _capture_read_only,
    _pump,
    _snapshot,
    _spawn,
    _visible_text,
)


SOURCE = "task-3/local/personal-memory"
CRITERIA = "task-3/local/guardrails"
OUTPUT = "task-3/participant/subtractive-first"
ARGV = (
    "sever",
    "--source",
    SOURCE,
    "--criteria",
    CRITERIA,
    "--save-as",
    OUTPUT,
    "--source-descendants",
    "--criteria-descendants",
)


def _study_ledger():
    from memcommit.profile_config import load_profile_registry
    from memcommit.store import MemoryStore
    from memcommit.study_action_log import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return StudyActionLedger(profile, store_dir=store.store_dir)


def _provider_event_count() -> int:
    return sum(
        event.action.startswith("PROVIDER_") for event in _study_ledger().list()
    )


def _bindings():
    from memcommit.authority.access import resolve_context_access
    from memcommit.commands.sever.command import _capture_binding
    from memcommit.store import MemoryStore

    store = MemoryStore(create=False)
    current = store.current_context_name()
    source_access = resolve_context_access(
        store,
        SOURCE,
        current_name=current,
        required_permission="READ",
    )
    criteria_access = resolve_context_access(
        store,
        CRITERIA,
        current_name=current,
        required_permission="READ",
    )
    return (
        store,
        _capture_binding(source_access, include_descendants=True),
        _capture_binding(criteria_access, include_descendants=True),
    )


def _capture_command(
    args: tuple[str, ...], *, stem: str, expected: tuple[str, ...]
) -> float:
    child, recorder = _spawn(*args)
    started = time.monotonic()
    try:
        _pump(child, recorder, seconds=30, require_eof=True)
        elapsed = time.monotonic() - started
        raw = recorder.getvalue()
        missing = [value for value in expected if value not in raw]
        if missing:
            raise RuntimeError(f"Command capture {stem} missed {missing!r}.")
        _snapshot(recorder, stem)
        return elapsed
    finally:
        if child.isalive():
            child.close(force=True)


def _verify_approved_sever_attempt() -> None:
    ledger = _study_ledger()
    for event in ledger.list():
        if (
            event.action != "COMMAND_STARTED"
            or event.data.get("operation") != "sever"
        ):
            continue
        attempt = ledger.events_for_attempt(event.attempt_uid)
        actions = {item.action for item in attempt}
        if "APPROVAL_ACCEPTED" not in actions:
            continue
        if any(item.action.startswith("PROVIDER_") for item in attempt):
            raise RuntimeError("Exact Sever approval attempt contacted a provider.")
        required = {
            "APPROVAL_PRESENTED",
            "APPROVAL_ACCEPTED",
            "COMMAND_FINISHED",
        }
        if not required.issubset(actions):
            raise RuntimeError("Exact Sever approval evidence is incomplete.")
        return
    raise RuntimeError("No approved Sever attempt was recorded.")


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from memcommit.profile_config import load_profile_registry
    from memcommit.sever_store import SeverSessionStore

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")
    store, source_before, criteria_before = _bindings()
    if len(source_before.memories) != 300 or len(criteria_before.memories) != 75:
        raise RuntimeError("Task 3 Sever baseline is not 300 by 75.")
    if store.context_exists(OUTPUT):
        raise RuntimeError(f"Task 3 Sever output {OUTPUT!r} already exists.")
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "MEM SEVER" in visible and "REVIEWING · 300 SOURCE" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for exact Task 3 Sever.")
        elapsed_to_review = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in (SOURCE, CRITERIA, OUTPUT, "REVIEWING · 300 SOURCE"):
            if value not in visible:
                raise RuntimeError(f"Task 3 Sever screen missed {value!r}.")
        _snapshot(recorder, "103-task3-sever-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "SEVER ASSESSMENT" not in visible or "SOURCE MEMORY" not in visible:
            raise RuntimeError("Task 3 Sever candidate detail did not open.")
        if "✓ 1. Use recommendation · FORGET" not in visible:
            child.send("\r")
            _pump(child, recorder, seconds=0.5)
            if "✓ 1. Use recommendation · FORGET" not in _visible_text(
                recorder
            ):
                raise RuntimeError("Task 3 Sever recommendation was not restored.")
        _snapshot(recorder, "104-task3-sever-candidate-detail")

        child.send("\x1b")
        _pump(child, recorder, seconds=1.0)
        visible = _visible_text(recorder)
        if (
            not child.isalive()
            or "MEM SEVER · LOCAL CONTENT REVIEW" not in visible
            or "SEVER DECISION 1/300" in visible
        ):
            raise RuntimeError("Task 3 Sever candidate detail did not close.")
        child.send("a")
        _pump(child, recorder, seconds=0.7)
        if "REVIEW AND APPLY" not in _visible_text(recorder):
            raise RuntimeError("Task 3 Sever final review did not open.")
        _snapshot(recorder, "105-task3-sever-final-review")

        child.send("\x1b[B")
        _pump(child, recorder, seconds=0.5)
        if "APPLY" not in _visible_text(recorder):
            raise RuntimeError("Task 3 Sever exact Apply action is not visible.")
        _snapshot(recorder, "106-task3-sever-exact-approval")

        child.send("\r")
        _pump(child, recorder, seconds=30, require_eof=True)
        elapsed_review_and_apply = time.monotonic() - started
        raw = recorder.getvalue()
        if (
            "ANALYSIS · EXACT PREWARM · PROVIDER NOT CALLED" not in raw
            or "SEVER · APPLIED · SOURCE UNCHANGED" not in raw
            or "OUTPUT · task-3/participant/subtractive-first · CREATED LOCALLY"
            not in raw
        ):
            raise RuntimeError("Task 3 Sever did not publish its exact receipt.")
        _snapshot(recorder, "107-task3-sever-apply-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    sessions = SeverSessionStore(store).list()
    applied = next(
        (
            item
            for item in sessions
            if item.output_name == OUTPUT and item.state == "APPLIED"
        ),
        None,
    )
    store, source_after, criteria_after = _bindings()
    if (
        applied is None
        or applied.state != "APPLIED"
        or len(applied.candidates) != 300
        or any(candidate.recommendation != "FORGET" for candidate in applied.candidates)
        or source_after.frame_digest != source_before.frame_digest
        or len(source_after.memories) != 300
        or criteria_after.frame_digest != criteria_before.frame_digest
        or not store.context_exists(OUTPUT)
        or len(tuple(store.load_direct(OUTPUT).iter_items())) != 0
    ):
        raise RuntimeError("Applied Task 3 Sever failed its durable contract.")

    _capture_read_only(
        ("show", "--context", OUTPUT),
        stem="108-task3-sever-empty-result-verification",
        expected=(OUTPUT, "Memories 0"),
    )
    _capture_read_only(
        ("show", "--context", SOURCE),
        stem="109-task3-sever-source-verification",
        expected=(SOURCE, "Memories 0", "Embedded Contexts 4"),
    )
    undo_seconds = _capture_command(
        ("undo",),
        stem="110-task3-sever-undo-receipt",
        expected=("Undid command: mem sever", "Affected Contexts:"),
    )
    if store.context_exists(OUTPUT):
        raise RuntimeError("Sever Undo did not remove its new output Context.")
    redo_seconds = _capture_command(
        ("redo",),
        stem="111-task3-sever-redo-receipt",
        expected=("Redid command: mem sever", "Affected Contexts:"),
    )
    if not store.context_exists(OUTPUT):
        raise RuntimeError("Sever Redo did not restore its output Context.")
    _capture_read_only(
        ("show", "--context", OUTPUT),
        stem="112-task3-sever-restored-result-verification",
        expected=(OUTPUT, "Memories 0"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "35"),
        stem="113-task3-sever-action-log",
        expected=(
            "operation=sever",
            "APPROVAL_PRESENTED",
            "APPROVAL_ACCEPTED",
            "operation=undo",
            "operation=redo",
        ),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 3 Sever replay contacted a provider.")
    _verify_approved_sever_attempt()
    (OUT / "task3-sever-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_review_seconds": elapsed_to_review,
                "elapsed_review_and_apply_seconds": elapsed_review_and_apply,
                "undo_seconds": undo_seconds,
                "redo_seconds": redo_seconds,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "source_memories_before": 300,
                "source_memories_after": len(source_after.memories),
                "criteria_memories": 75,
                "recommendations": {"FORGET": 300},
                "output_memories": 0,
                "source_frame_digest_before": source_before.frame_digest,
                "source_frame_digest_after": source_after.frame_digest,
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
