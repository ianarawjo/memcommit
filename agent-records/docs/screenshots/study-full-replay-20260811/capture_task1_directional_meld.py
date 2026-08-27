"""Replay the exact Task 1 directional Meld and verify its granted target."""

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


INCOMING = "task-1/participant/construction-updates"
BASELINE = "task-1/campus-wiki"
ARGV = (
    "meld",
    INCOMING,
    "--left-descendants",
    "--into",
    BASELINE,
    "--right-descendants",
)


def _study_ledger():
    from memcommit.application.operations.profile.config import load_profile_registry
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.command_ledger.study_actions import StudyActionLedger

    profile = load_profile_registry().active
    store = MemoryStore(create=False)
    return StudyActionLedger(profile, store_dir=store.store_dir)


def _provider_event_count() -> int:
    return sum(event.action.startswith("PROVIDER_") for event in _study_ledger().list())


def _load_scopes():
    from memcommit.application.authority.access import (
        GrantedReadStore,
        resolve_context_access,
    )
    from memcommit.core.context_targeting.loading import load_context_scope
    from memcommit.persistence.store import MemoryStore

    store = MemoryStore(create=False)
    current = store.current_context_name()
    frames = []
    for name in (INCOMING, BASELINE):
        access = resolve_context_access(
            store,
            name,
            current_name=current,
            required_permission="READ",
        )
        reader = GrantedReadStore(access) if access.is_granted else store
        frames.append(
            load_context_scope(
                reader,
                access.display_name if access.is_granted else access.context_name,
                include_descendants=True,
            )
        )
    return store, tuple(frames)


def _memory_count(context) -> int:
    from memcommit.context import Context, Memory

    seen: set[str] = set()

    def visit(current: Context) -> int:
        if current.uid in seen:
            return 0
        seen.add(current.uid)
        return sum(
            1
            if isinstance(item, Memory)
            else visit(item)
            if isinstance(item, Context)
            else 0
            for item in current.iter_items()
        )

    return visit(context)


def _verify_latest_attempt() -> None:
    ledger = _study_ledger()
    attempt = None
    for event in ledger.list():
        if event.action != "COMMAND_STARTED" or event.data.get("operation") != "meld":
            continue
        candidate = ledger.events_for_attempt(event.attempt_uid)
        if "APPROVAL_ACCEPTED" in {item.action for item in candidate}:
            attempt = candidate
            break
    if attempt is None:
        raise RuntimeError("No approved directional Meld attempt was recorded.")
    if any(event.action.startswith("PROVIDER_") for event in attempt):
        raise RuntimeError("Exact Task 1 directional Meld contacted a provider.")
    required = {"APPROVAL_PRESENTED", "APPROVAL_ACCEPTED", "COMMAND_FINISHED"}
    if not required.issubset({event.action for event in attempt}):
        raise RuntimeError("Directional Meld is missing exact approval evidence.")


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


def _approved_attempt_seconds() -> float:
    ledger = _study_ledger()
    for event in ledger.list():
        if event.action != "COMMAND_STARTED" or event.data.get("operation") != "meld":
            continue
        attempt = ledger.events_for_attempt(event.attempt_uid)
        if "APPROVAL_ACCEPTED" not in {item.action for item in attempt}:
            continue
        finished = next(item for item in attempt if item.action == "COMMAND_FINISHED")
        assert finished.elapsed_seconds is not None
        return finished.elapsed_seconds
    raise RuntimeError("No approved directional Meld attempt was recorded.")


def _owner_counts(session) -> dict[str, int]:
    assessment = session.current_assessment
    assert assessment is not None
    counts: dict[str, int] = {}
    for proposal in assessment.proposals:
        owner = proposal.owner_context_name or BASELINE
        counts[owner] = counts.get(owner, 0) + 1
    return dict(sorted(counts.items()))


def _finish_applied_replay(
    *,
    store,
    incoming_after,
    baseline_after,
    session,
    provider_events_before: int,
    elapsed_to_review: float,
) -> None:
    _capture_command(
        (*ARGV, "--accept"),
        stem="40-task1-directional-meld-apply-receipt",
        expected=(
            "State: APPLIED",
            "Recovered the prior meld application; no duplicate checkpoint",
        ),
    )
    _capture_read_only(
        ("show", "--context", "task-1/campus-wiki/building-access"),
        stem="41-task1-directional-meld-target-verification",
        expected=("task-1/campus-wiki/building-access", "Memories"),
    )
    _capture_read_only(
        ("show", "--context", INCOMING),
        stem="42-task1-directional-meld-source-verification",
        expected=(INCOMING, "Memories"),
    )
    _capture_read_only(
        ("log", "--actions", "--limit", "25"),
        stem="43-task1-directional-meld-action-log",
        expected=(
            "operation=meld",
            "APPROVAL_PRESENTED",
            "APPROVAL_ACCEPTED",
            "COMMAND_FINISHED",
        ),
    )

    provider_events_after = _provider_event_count()
    if provider_events_after != provider_events_before:
        raise RuntimeError("Task 1 directional Meld unexpectedly contacted a provider.")
    _verify_latest_attempt()
    assessment = session.current_assessment
    assert assessment is not None
    (OUT / "task1-directional-meld-replay-metrics.json").write_text(
        json.dumps(
            {
                "command": "mem " + " ".join(ARGV),
                "profile": PROFILE_NAME,
                "captured_review_and_apply_seconds": elapsed_to_review,
                "provider_events_before": provider_events_before,
                "provider_events_after": provider_events_after,
                "incoming_memories_before": 75,
                "incoming_memories_after": _memory_count(incoming_after),
                "baseline_memories_before": 300,
                "baseline_memories_after": _memory_count(baseline_after),
                "relations": len(session.comparison_seed.analysis.relations),
                "issues": len(assessment.issues),
                "proposals": len(assessment.proposals),
                "owner_counts": _owner_counts(session),
                "origin": "EXACT_PREWARM",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from memcommit.application.operations.profile.config import load_profile_registry

    if load_profile_registry().active.name != PROFILE_NAME:
        raise RuntimeError(f"Expected active replay Profile {PROFILE_NAME!r}.")

    store, (incoming_before, baseline_before) = _load_scopes()
    existing = store.load_meld_session(baseline_before.uid)
    if (
        _memory_count(incoming_before) == 75
        and _memory_count(baseline_before) == 375
        and existing is not None
        and existing.state == "APPLIED"
    ):
        _finish_applied_replay(
            store=store,
            incoming_after=incoming_before,
            baseline_after=baseline_before,
            session=existing,
            provider_events_before=_provider_event_count(),
            elapsed_to_review=_approved_attempt_seconds(),
        )
        return
    if _memory_count(incoming_before) != 75 or _memory_count(baseline_before) != 300:
        raise RuntimeError("Task 1 directional Meld baseline is not 75 into 300.")
    if existing is None or existing.state != "READY_TO_APPLY":
        raise RuntimeError("Exact Task 1 directional Meld session is not ready.")
    from memcommit.study_scenarios.legacy.prewarm.meld_directional import (
        find_installed_exact_directional_meld_prewarm,
    )

    if (
        find_installed_exact_directional_meld_prewarm(
            store=store,
            current=existing,
        )
        is None
    ):
        raise RuntimeError("Directional Meld does not match the installed prewarm.")
    provider_events_before = _provider_event_count()

    child, recorder = _spawn(*ARGV)
    started = time.monotonic()
    try:
        deadline = started + 10
        while time.monotonic() < deadline:
            _pump(child, recorder, seconds=0.05)
            visible = _visible_text(recorder)
            if "DIRECTIONAL" in visible and "READY_TO_APPLY" in visible:
                break
        else:
            raise RuntimeError("Timed out waiting for exact directional Meld.")
        elapsed_to_review = time.monotonic() - started
        _pump(child, recorder, seconds=0.5)
        visible = _visible_text(recorder)
        for value in (
            "DIRECTIONAL",
            "READY_TO_APPLY",
            "51 RELATIONS",
            "75 CHANGES",
            "75/375 SOURCE COVERAGE",
        ):
            if value not in visible:
                raise RuntimeError(f"Directional Meld screen missed {value!r}.")
        _snapshot(recorder, "36-task1-directional-meld-exact-entry")

        child.send("\t\x1b[B\r")
        _pump(child, recorder, seconds=0.8)
        visible = _visible_text(recorder)
        if "SOURCE CLAIMS" not in visible or "CLASSIFICATION" not in visible:
            raise RuntimeError("Directional relation detail did not open.")
        _snapshot(recorder, "37-task1-directional-meld-relation-detail")

        child.send("\x08")
        _pump(child, recorder, seconds=0.5)
        child.send("a")
        _pump(child, recorder, seconds=0.7)
        visible = _visible_text(recorder)
        if "REVIEW AND APPLY" not in visible:
            raise RuntimeError("Directional Meld final review did not open.")
        _snapshot(recorder, "38-task1-directional-meld-final-review")

        child.send("\x1b[B")
        _pump(child, recorder, seconds=0.5)
        if "APPLY" not in _visible_text(recorder):
            raise RuntimeError("Directional Meld exact Apply action is not visible.")
        _snapshot(recorder, "39-task1-directional-meld-exact-approval")

        child.send("\r")
        _pump(child, recorder, seconds=30, require_eof=True)
        raw = recorder.getvalue()
        if "Applied 75 meld changes" not in raw or "State: APPLIED" not in raw:
            raise RuntimeError("Directional Meld did not publish its applied receipt.")
        _snapshot(recorder, "40-task1-directional-meld-apply-receipt")
    finally:
        if child.isalive():
            child.close(force=True)

    _, (incoming_after, baseline_after) = _load_scopes()
    session = store.load_meld_session(baseline_after.uid)
    if (
        session is None
        or session.mode != "DIRECTIONAL"
        or session.state != "APPLIED"
        or _memory_count(incoming_after) != 75
        or _memory_count(baseline_after) != 375
        or len(session.current_assessment.proposals) != 75
    ):
        raise RuntimeError("Applied directional Meld failed its durable contract.")

    _finish_applied_replay(
        store=store,
        incoming_after=incoming_after,
        baseline_after=baseline_after,
        session=session,
        provider_events_before=provider_events_before,
        elapsed_to_review=elapsed_to_review,
    )


if __name__ == "__main__":
    main()
