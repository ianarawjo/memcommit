"""Focused rendering tests for directional and symmetric Meld shell chrome."""
from types import SimpleNamespace

import memcommit.interfaces.tui.operations.meld.screen as meld_shell


def _text(session, *, expanded=False) -> str:
    return "".join(
        fragment
        for _, fragment in meld_shell._screen_text(
            session,
            selected_index=0,
            expanded=expanded,
            choice_index=None,
        )
    )


def _directional_session(*, proposals, state="READY_TO_APPLY"):
    incoming_memory = SimpleNamespace(
        uid="incoming-memory",
        content="Only the vehicle entrance is closed.",
        position=0,
    )
    baseline_memory = SimpleNamespace(
        uid="baseline-memory",
        content="The parking stairwell is closed.",
        position=0,
    )
    incoming = SimpleNamespace(
        uid="incoming-frame",
        role="INCOMING",
        context_name="test/update/from",
        memories=(incoming_memory,),
    )
    baseline = SimpleNamespace(
        uid="baseline-frame",
        role="BASELINE",
        context_name="test/update/to",
        memories=(baseline_memory,),
    )
    relation = SimpleNamespace(
        uid="relation-1",
        kind="CORRECTS",
        status="RESOLVED",
        reason="The incoming statement narrows what is closed.",
        members=(
            SimpleNamespace(
                frame_uid=incoming.uid,
                memory_uid=incoming_memory.uid,
            ),
            SimpleNamespace(
                frame_uid=baseline.uid,
                memory_uid=baseline_memory.uid,
            ),
        ),
    )
    issue = SimpleNamespace(
        uid="issue-1",
        priority="HELPFUL",
        title="Parking closure scope",
        why_it_matters="The baseline currently closes too much.",
        question="Should the stairwell remain open?",
        options=(),
        relation_uids=(relation.uid,),
    )
    return SimpleNamespace(
        mode="DIRECTIONAL",
        frames=(incoming, baseline),
        target=SimpleNamespace(context_name=baseline.context_name),
        state=state,
        current_assessment=SimpleNamespace(
            overview="The incoming correction narrows the parking closure.",
            relations=(relation,),
            issues=(issue,),
            proposals=tuple(proposals),
        ),
    )


def test_directional_screen_exposes_roles_route_and_exact_operations():
    edit = SimpleNamespace(
        operation="EDIT",
        disposition="SYNTHESIZE",
        content="The stairwell remains open; only vehicle access is closed.",
        relation_uids=("relation-1",),
    )
    addition = SimpleNamespace(
        operation="ADD",
        disposition="PRESERVE",
        content="Pedestrians may continue to use the parking entrance.",
        relation_uids=("relation-1",),
    )

    rendered = _text(
        _directional_session(proposals=(edit, addition)),
        expanded=True,
    )

    assert (
        "INCOMING test/update/from → BASELINE / TARGET test/update/to"
        in rendered
    )
    assert "[INCOMING] test/update/from #1" in rendered
    assert "[BASELINE] test/update/to #1" in rendered
    assert "PROPOSED BASELINE CHANGES" in rendered
    assert "~  1. [EDIT · SYNTHESIZE]" in rendered
    assert "+  2. [ADD · PRESERVE]" in rendered
    assert "2 changes" in rendered


def test_directional_ready_zero_change_is_not_rendered_as_incomplete():
    rendered = _text(_directional_session(proposals=()))

    assert "0 changes" in rendered
    assert (
        "no baseline changes proposed; ready to accept this no-change result"
        in rendered
    )
    assert "(none yet)" not in rendered


def test_symmetric_screen_keeps_peer_route_and_result_vocabulary():
    left = SimpleNamespace(
        uid="left-frame",
        role="PEER",
        context_name="left",
        memories=(),
    )
    right = SimpleNamespace(
        uid="right-frame",
        role="PEER",
        context_name="right",
        memories=(),
    )
    proposal = SimpleNamespace(
        operation="ADD",
        disposition="PRESERVE",
        content="Keep the peer-supported distinction.",
        relation_uids=(),
    )
    session = SimpleNamespace(
        mode="SYMMETRIC",
        frames=(left, right),
        target=SimpleNamespace(context_name="result"),
        state="READY_TO_APPLY",
        current_assessment=SimpleNamespace(
            overview="Both peer sources remain represented.",
            relations=(),
            issues=(),
            proposals=(proposal,),
        ),
    )

    rendered = _text(session)

    assert "left + right → result" in rendered
    assert "PROPOSED TARGET MEMORIES" in rendered
    assert "+  1. [PRESERVE]" in rendered
    assert "1 results" in rendered
    assert "[PEER]" not in rendered


def test_shell_non_tty_hint_refers_to_the_same_command(monkeypatch):
    seen: dict[str, str] = {}

    def require_terminal(label, *, snapshot_hint):
        seen["label"] = label
        seen["hint"] = snapshot_hint

    monkeypatch.setattr(
        meld_shell,
        "require_interactive_terminal",
        require_terminal,
    )
    session = SimpleNamespace(current_assessment=None)

    assert meld_shell.run_meld_shell(session) is None
    assert seen == {
        "label": "Interactive meld",
        "hint": (
            "Run the same 'mem meld' command outside a TTY to render its "
            "saved snapshot."
        ),
    }
