"""Apply, verify, and undo the exact Task 1 Update in the Study replay."""

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


SOURCE = "task-1/participant/construction-updates"
TARGET = "task-1/campus-wiki"
TARGET_CHILD = "task-1/campus-wiki/building-access"
BASELINE_TEXT = (
    "The Main Building third-floor rear entrance may be used for general "
    "passage during regular opening hours in both the academic term and recess."
)
APPLIED_TEXT = (
    "The Main Building third-floor rear entrance may normally be used for "
    "general passage during regular opening hours in both the academic term "
    "and recess, but it cannot be used for general passage during the "
    "construction period."
)
ARGV = (
    "update",
    "--from",
    SOURCE,
    "--to",
    TARGET,
    "--source-descendants",
    "--target-descendants",
)


def _require_visible(recorder, *expected: str) -> None:
    visible = _visible_text(recorder)
    missing = [value for value in expected if value not in visible]
    if missing:
        raise RuntimeError(f"Task 1 Update screen missed expected text: {missing!r}")


def _study_ledger():
    from memcommit.application.operations.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return StudyActionLedger(profile, store_dir=store.store_dir)


def _provider_event_count() -> int:
    return sum(event.action.startswith("PROVIDER_") for event in _study_ledger().list())


def _load_inputs():
    from memcommit.application.capabilities.authority.context_access import (
        GrantedReadStore,
        freeze_granted_context_binding,
        resolve_context_access,
    )
    from memcommit.application.capabilities.context_scope_loading import (
        load_context_scope,
    )
    from memcommit.persistence.store import MemoryStore
    from memcommit.application.operations.update.model import collect_update_inputs

    store = MemoryStore(create=False)
    current = store.current_context_name()
    source_access = resolve_context_access(
        store,
        SOURCE,
        current_name=current,
        required_permission="READ",
    )
    target_access = resolve_context_access(
        store,
        TARGET,
        current_name=current,
        required_permission="READ",
    )
    source_store = (
        GrantedReadStore(source_access) if source_access.is_granted else store
    )
    target_store = (
        GrantedReadStore(target_access) if target_access.is_granted else store
    )
    source = load_context_scope(
        source_store,
        source_access.display_name
        if source_access.is_granted
        else source_access.context_name,
        include_descendants=True,
    )
    target = load_context_scope(
        target_store,
        target_access.display_name
        if target_access.is_granted
        else target_access.context_name,
        include_descendants=True,
    )
    return (
        store,
        source,
        target,
        collect_update_inputs(source, target),
        freeze_granted_context_binding(target_access)
        if target_access.is_granted
        else None,
    )


def _capture_command(
    args: tuple[str, ...], *, stem: str, expected: tuple[str, ...]
) -> None:
    child, recorder = _spawn(*args)
    try:
        _pump(child, recorder, seconds=30, require_eof=True)
        raw = recorder.getvalue()
        missing = [value for value in expected if value not in raw]
        if missing:
            raise RuntimeError(f"Command capture {stem} missed {missing!r}.")
        _snapshot(recorder, stem)
    finally:
        if child.isalive():
            child.close(force=True)


def _verify_latest_update_attempt() -> None:
    ledger = _study_ledger()
    start = next(
        event
        for event in ledger.list()
        if event.action == "COMMAND_STARTED" and event.data.get("operation") == "update"
    )
    attempt = ledger.events_for_attempt(start.attempt_uid)
    if any(event.action.startswith("PROVIDER_") for event in attempt):
        raise RuntimeError("Exact Task 1 Update contacted a provider.")
    required = {"APPROVAL_PRESENTED", "APPROVAL_ACCEPTED", "COMMAND_FINISHED"}
    if not required.issubset({event.action for event in attempt}):
        raise RuntimeError("Task 1 Update is missing approval evidence.")


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profile.config import load_profile_registry
    from memcommit.study_scenarios.legacy.prewarm.update import (
        is_installed_update_prewarm,
    )
    from memcommit.application.operations.update.model import (
        applied_session_matches,
        session_matches,
    )

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")

    store, source, target, before, granted_target = _load_inputs()
    existing = store.load_staged_update()
    resuming_staged = existing is not None
    if existing is not None and (
        existing.status != "staged"
        or not session_matches(
            existing,
            source,
            target,
            granted_target=granted_target,
        )
        or not is_installed_update_prewarm(store, existing)
    ):
        raise RuntimeError("Replay has a nonmatching existing Update receipt.")
    if len(before.source_candidates) != 75 or len(before.target_memories) != 300:
        raise RuntimeError(
            "Task 1 Update baseline is not the expected 75-to-300 frame."
        )
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "STAGED · 32 EDITS · 42 ADDITIONS" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for the exact Task 1 Update.")
        elapsed_to_plan = time.monotonic() - started
        _pump(child, recorder, seconds=0.4)
        if (
            not resuming_staged
            and "EXACT PREWARM · UPDATE PLAN REUSED" not in recorder.getvalue()
        ):
            raise RuntimeError("Update did not disclose exact-prewarm reuse.")
        _require_visible(
            recorder,
            "Staged update:",
            "32 EDITS · 42 ADDITIONS · 0 REMOVALS · 74 CHANGES",
            "APPLY is available",
        )
        _snapshot(recorder, "19-task1-update-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        _require_visible(recorder, "BEFORE", "AFTER", "SOURCE REFERENCES")
        _snapshot(recorder, "20-task1-update-edit-detail")

        child.send("a")
        _pump(child, recorder, seconds=0.6)
        _require_visible(
            recorder,
            "REVIEW AND APPLY",
            "Nothing changes until the final action below is confirmed",
        )
        _snapshot(recorder, "21-task1-update-final-review")

        child.send("\x1b[F")
        _pump(child, recorder, seconds=0.5)
        _require_visible(recorder, "APPLY", "Enter to apply the exact current proposal")
        _snapshot(recorder, "22-task1-update-exact-approval")

        child.send("\r")
        _pump(child, recorder, seconds=30, require_eof=True)
        raw = recorder.getvalue()
        if (
            f"Applied update: {SOURCE} -> {TARGET}" not in raw
            or f"Updated granted authority target {TARGET}." not in raw
        ):
            raise RuntimeError("Task 1 Update did not publish its applied receipt.")
        _snapshot(recorder, "23-task1-update-apply-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    _, applied_source, applied_target, applied_inputs, applied_binding = _load_inputs()
    applied = store.load_staged_update()
    if (
        applied is None
        or applied.status != "applied"
        or len(applied_inputs.target_memories) != 342
        or not applied_session_matches(
            applied,
            applied_source,
            applied_target,
            granted_target=applied_binding,
        )
    ):
        raise RuntimeError("Applied Task 1 Update failed its exact receipt check.")

    undo_captured = False
    try:
        _capture_read_only(
            ("show", "--context", TARGET_CHILD),
            stem="24-task1-update-applied-target",
            expected=(TARGET_CHILD, APPLIED_TEXT),
        )
    finally:
        # Restore the fixed Study target even when presentation verification
        # fails, so later exact prewarms still bind the original 300 Memories.
        current = store.load_staged_update()
        if current is not None and current.status == "applied":
            _capture_command(
                ("undo",),
                stem="25-task1-update-undo-receipt",
                expected=("Undid command: mem update", "Affected Contexts:"),
            )
            undo_captured = True
    if not undo_captured:
        raise RuntimeError("Task 1 Update was not restored through mem undo.")

    _, restored_source, restored_target, restored, restored_binding = _load_inputs()
    undone = store.load_staged_update()
    if (
        undone is None
        or undone.status != "undone"
        or len(restored.target_memories) != 300
        or restored.source_digest != before.source_digest
        or restored.target_digest != before.target_digest
        or not session_matches(
            undone,
            restored_source,
            restored_target,
            granted_target=restored_binding,
        )
    ):
        raise RuntimeError("mem undo did not restore the exact Task 1 baseline.")
    _capture_read_only(
        ("show", "--context", TARGET_CHILD),
        stem="26-task1-update-restored-target",
        expected=(TARGET_CHILD, BASELINE_TEXT),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "25"),
        stem="27-task1-update-action-log",
        expected=(
            "operation=update",
            "APPROVAL_PRESENTED",
            "APPROVAL_ACCEPTED",
            "operation=undo",
        ),
    )

    if _provider_event_count() != provider_events_before:
        raise RuntimeError("Task 1 Update replay unexpectedly contacted a provider.")
    _verify_latest_update_attempt()
    (OUT / "task1-update-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "elapsed_to_plan_seconds": elapsed_to_plan,
                "provider_events_before": provider_events_before,
                "provider_events_after": _provider_event_count(),
                "source_memories": 75,
                "target_memories_before": 300,
                "target_memories_applied": 342,
                "target_memories_restored": 300,
                "target_digest_before": before.target_digest,
                "target_digest_applied": applied_inputs.target_digest,
                "target_digest_restored": restored.target_digest,
                "operations": {"edit": 32, "add": 42, "remove": 0},
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
