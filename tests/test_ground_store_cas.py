"""Atomic compare-and-swap contracts for persisted named Grounds."""
from __future__ import annotations

import multiprocessing

import memcommit.application.capabilities.ops as ops
from memcommit.application.operations.ground.model import (
    GroundSession,
    GroundTargetSpec,
    bind_ground_workbench,
    create_ground_session,
)
from memcommit.persistence.store import (
    ConcurrentGroundUpdateError,
    MemoryStore,
    ground_session_record_digest,
)
import pytest


def _with_goal(session: GroundSession, goal: str) -> GroundSession:
    data = session.to_dict()
    data["goal"] = goal
    return GroundSession.from_dict(data)


def _race_ground_save(
    session_data,
    expected_uid,
    expected_revision,
    expected_digest,
    start,
    outcomes,
):
    session = GroundSession.from_dict(session_data)
    start.wait()
    try:
        MemoryStore(create=False).save_ground_session(
            session,
            expected_uid=expected_uid,
            expected_revision=expected_revision,
            expected_digest=expected_digest,
        )
    except ConcurrentGroundUpdateError:
        outcomes.put("STALE")
    else:
        outcomes.put(f"SAVED:{session.goal}")


def _bound_ground(store: MemoryStore) -> tuple[GroundSession, tuple]:
    raw = ops.init("ground/raw")
    raw.add("Raw evidence.")
    derived = ops.init("ground/derived")
    derived.add("Derived candidate.")
    target = ops.init("ground/target")
    for context in (raw, derived, target):
        store.save(context)
    session = bind_ground_workbench(
        create_ground_session("atomic-bound-ground", goal="Review evidence."),
        description="Build one reviewed target.",
        raw_context=raw,
        derived_context=derived,
        target_contexts=(target,),
        target_requirements=(
            GroundTargetSpec(
                context_name=target.name,
                description="Publish one supported result.",
                role="PUBLICATION_TARGET",
            ),
        ),
    )
    store.save_ground_session(session)
    return session, (raw, derived, target)


def test_ground_save_cas_accepts_the_exact_persisted_record(isolated_store):
    store = MemoryStore()
    original = create_ground_session("atomic-ground", goal="Original.")
    store.save_ground_session(original)
    changed = _with_goal(original, "Approved replacement.")

    store.save_ground_session(
        changed,
        expected_uid=original.uid,
        expected_revision=original.revision,
        expected_digest=ground_session_record_digest(original),
    )

    assert store.load_ground_session("atomic-ground") == changed


def test_ground_save_cas_rejects_a_change_after_proposal(isolated_store):
    store = MemoryStore()
    original = create_ground_session("atomic-ground", goal="Original.")
    store.save_ground_session(original)
    approved_candidate = _with_goal(original, "Approved candidate.")
    competing_change = _with_goal(original, "Competing change.")
    store.save_ground_session(competing_change)

    with pytest.raises(
        ConcurrentGroundUpdateError,
        match="changed before it could be saved",
    ):
        store.save_ground_session(
            approved_candidate,
            expected_uid=original.uid,
            expected_revision=original.revision,
            expected_digest=ground_session_record_digest(original),
        )

    assert store.load_ground_session("atomic-ground") == competing_change


def test_ground_save_cas_rejects_a_deleted_expected_record(isolated_store):
    store = MemoryStore()
    original = create_ground_session("atomic-ground", goal="Original.")

    with pytest.raises(
        ConcurrentGroundUpdateError,
        match="no longer exists",
    ):
        store.save_ground_session(
            original,
            expected_uid=original.uid,
            expected_revision=original.revision,
            expected_digest=ground_session_record_digest(original),
        )

    assert store.load_ground_session("atomic-ground") is None


def test_ground_save_cas_serializes_competing_processes(isolated_store):
    store = MemoryStore()
    original = create_ground_session("atomic-ground", goal="Original.")
    store.save_ground_session(original)
    candidates = (
        _with_goal(original, "Candidate A."),
        _with_goal(original, "Candidate B."),
    )
    expected_digest = ground_session_record_digest(original)
    process_context = multiprocessing.get_context("fork")
    start = process_context.Event()
    outcomes = process_context.Queue()
    processes = [
        process_context.Process(
            target=_race_ground_save,
            args=(
                candidate.to_dict(),
                original.uid,
                original.revision,
                expected_digest,
                start,
                outcomes,
            ),
        )
        for candidate in candidates
    ]

    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=5)
        assert process.exitcode == 0

    results = {outcomes.get(timeout=1) for _ in processes}
    assert "STALE" in results
    saved = [result for result in results if result.startswith("SAVED:")]
    assert len(saved) == 1
    assert store.load_ground_session("atomic-ground").goal in {
        "Candidate A.",
        "Candidate B.",
    }


def test_ground_save_can_verify_all_bound_frames_atomically(isolated_store):
    store = MemoryStore()
    session, _contexts = _bound_ground(store)

    store.save_ground_session(
        session,
        expected_uid=session.uid,
        expected_revision=session.revision,
        expected_digest=ground_session_record_digest(session),
        verify_bound_frames=True,
    )

    assert store.load_ground_session("atomic-bound-ground") == session


def test_ground_save_frame_verification_rejects_changed_context(
    isolated_store,
):
    store = MemoryStore()
    session, (raw, _derived, _target) = _bound_ground(store)
    current_raw = store.load_direct(raw.name)
    current_raw.add("Late evidence.")
    store.save(current_raw)

    with pytest.raises(
        ConcurrentGroundUpdateError,
        match="Bound Context 'ground/raw' changed",
    ):
        store.save_ground_session(
            session,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
            verify_bound_frames=True,
        )

    assert store.load_ground_session("atomic-bound-ground") == session


def test_ground_save_frame_verification_rejects_deleted_context(
    isolated_store,
):
    store = MemoryStore()
    session, (raw, _derived, _target) = _bound_ground(store)
    store.delete(raw.name)

    with pytest.raises(
        ConcurrentGroundUpdateError,
        match="Bound Context 'ground/raw' no longer exists",
    ):
        store.save_ground_session(
            session,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
            verify_bound_frames=True,
        )


def test_ground_save_frame_verification_rejects_recreated_context(
    isolated_store,
):
    store = MemoryStore()
    session, (raw, _derived, _target) = _bound_ground(store)
    store.delete(raw.name)
    replacement = ops.init(raw.name)
    replacement.add("Raw evidence.")
    store.save(replacement)

    with pytest.raises(
        ConcurrentGroundUpdateError,
        match="Bound Context 'ground/raw' changed",
    ):
        store.save_ground_session(
            session,
            expected_uid=session.uid,
            expected_revision=session.revision,
            expected_digest=ground_session_record_digest(session),
            verify_bound_frames=True,
        )


def test_ground_setup_save_keeps_frame_verification_opt_in(isolated_store):
    store = MemoryStore()
    session, (raw, _derived, _target) = _bound_ground(store)
    current_raw = store.load_direct(raw.name)
    current_raw.add("Late evidence.")
    store.save(current_raw)

    store.save_ground_session(session)

    assert store.load_ground_session("atomic-bound-ground") == session


def test_ground_frame_verification_requires_a_bound_ground(isolated_store):
    store = MemoryStore()
    session = create_ground_session("atomic-ground", goal="Original.")

    with pytest.raises(ValueError, match="requires a bound Ground"):
        store.save_ground_session(session, verify_bound_frames=True)

    assert store.load_ground_session("atomic-ground") is None


@pytest.mark.parametrize(
    "expectations",
    [
        {"expected_uid": "uid"},
        {"expected_revision": 0},
        {"expected_digest": "0" * 64},
        {
            "expected_uid": "uid",
            "expected_revision": 0,
        },
    ],
)
def test_ground_save_cas_requires_a_complete_expected_record(
    isolated_store,
    expectations,
):
    store = MemoryStore()
    session = create_ground_session("atomic-ground", goal="Original.")

    with pytest.raises(ValueError, match="must be supplied together"):
        store.save_ground_session(session, **expectations)

    assert store.load_ground_session("atomic-ground") is None
