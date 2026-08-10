"""Persistent semantic review state and prompt-toolkit shell contracts."""
from __future__ import annotations

import json

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
from memcommit.cli import app
from memcommit.commands.review_shell import (
    RESPONSE_LABEL,
    render_review_snapshot,
    run_review_shell,
    safe_terminal_text,
)
from memcommit.commands.review_resolution_shell import (
    review_resolution_view,
    run_review_resolution_shell,
)
from memcommit.context import Memory
from memcommit.findings import (
    AmbiguityFinding,
    AmbiguityReport,
)
from memcommit.review import (
    ReviewError,
    ReviewSession,
    create_ambiguity_review,
    review_matches_context,
)
from memcommit.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "QUALITY FIND PAYLOAD:\n"


class PayloadProvider:
    def __init__(self, responder):
        self.responder = responder
        self.calls: list[dict] = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "find_ambiguities"
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append(payload)
        return json.dumps(self.responder(payload))


def _context_and_report():
    ctx = ops.init("review/context")
    first = ops.add(ctx, "같은 NFC를 쓴다.")
    ops.add(ctx, "직원 출입구는 계속 열린다.")
    third = ops.add(ctx, "담당자에게 문의한다.")
    report = AmbiguityReport(
        memory_count=3,
        # Return provider-like reverse order to exercise local restoration.
        findings=(
            AmbiguityFinding(
                memory=third,
                interpretation="SINGLE",
                clarification="HELPFUL",
                ordinary_readings=(
                    "Ask the person responsible for this matter.",
                ),
                reason=(
                    "The responsible person is not named; clarification "
                    "would help identify a contact while the instruction "
                    "remains usable."
                ),
                question="Who is the responsible person?",
            ),
            AmbiguityFinding(
                memory=first,
                interpretation="DOMINANT",
                clarification="REQUIRED",
                ordinary_readings=(
                    "The door uses the previously described NFC mechanism.",
                    "The door accepts the same credential and permission rule.",
                ),
                reason=(
                    "“same NFC” has a dominant mechanism reading and a live "
                    "credential alternative; clarification is required "
                    "because the accepted credential cannot be determined."
                ),
                question="Does “same NFC” mean the mechanism or credential?",
            ),
        ),
    )
    return ctx, report, first, third


def test_review_projects_into_common_response_workbench_without_schema_changes():
    ctx, report, first, _third = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    response = session.response_for(first.uid)
    response.selected_choice_uid = session.items[0].choices[1].uid
    response.text = "It refers to the staff credential."

    view = review_resolution_view(session, ctx)
    item = view.item(first.uid)

    assert view.list_label == "ACTIONABLE FINDINGS"
    assert view.capabilities == frozenset({"SUBMIT_ITEM"})
    assert item.issue_presentation is not None
    assert item.issue_presentation.evidence[0].sources[0].content == first.content
    assert item.selected_option_uid == response.selected_choice_uid
    assert item.response_text == response.text
    assert session.to_dict()["schema_version"] == 2


def test_common_review_response_frame_persists_choice_and_comment():
    ctx, report, first, _third = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    saved: list[dict[str, object]] = []

    with create_pipe_input() as pipe_input:
        # Open the first finding, enter RESPONSES on reading 1, choose reading
        # 2, then move to its independent Response box.
        pipe_input.send_text(
            "\t\x1b[B\r\t\x1b[B\r\x1b[B\r"
            "교직원 출입구의 자격 규칙이다.\rq"
        )
        result = run_review_resolution_shell(
            session,
            ctx,
            save=lambda value: saved.append(value.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    response = result.response_for(first.uid)
    assert response.selected_choice_uid == session.items[0].choices[1].uid
    assert response.text == "교직원 출입구의 자격 규칙이다."
    assert saved


def test_review_restores_source_order_and_derives_reading_roles():
    ctx, report, first, third = _context_and_report()

    session = create_ambiguity_review(ctx, report)

    assert [item.uid for item in session.items] == [first.uid, third.uid]
    assert [choice.label for choice in session.items[0].choices] == [
        "DOMINANT",
        "ALTERNATIVE",
    ]
    assert [choice.label for choice in session.items[1].choices] == [
        "SINGLE",
    ]
    assert session.sort_mode == "SOURCE"
    session.toggle_sort()
    assert [item.uid for item in session.ordered_items()] == [
        first.uid,
        third.uid,
    ]


def test_review_uses_one_combined_response_for_selection_refinement_or_new_reading():
    ctx, report, first, _ = _context_and_report()
    session = create_ambiguity_review(ctx, report)

    session.select_choice(0)
    response = session.response_for(first.uid)
    response.text = (
        "위 해석이 맞지만 이 문에서는 출입 권한이 교직원으로 제한된다."
    )

    restored = ReviewSession.from_dict(session.to_dict())
    restored_response = restored.response_for(first.uid)
    assert restored_response.selected_choice_uid.endswith(":reading:1")
    assert restored_response.text == response.text

    # The same field also represents a different reading when no proposal is
    # selected; the shell deliberately does not guess a subtype.
    restored.select_choice(None)
    restored_response.text = "A different reading supplied by the reviewer."
    assert restored_response.selected_choice_uid is None
    assert restored_response.answered


def test_snapshot_has_one_response_field_and_sanitizes_terminal_controls():
    ctx, report, _, _ = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    session.items[0].choices[0].text  # frozen semantic input remains unchanged
    session.response_for(session.items[0].uid).text = "설명\x1b[31m"

    snapshot = render_review_snapshot(session, ctx)

    assert snapshot.count(RESPONSE_LABEL) == 1
    assert "[DOMINANT]" in snapshot
    assert "[ALTERNATIVE]" in snapshot
    assert "WHY THIS IS UNCLEAR" in snapshot
    assert "\x1b" not in snapshot
    assert safe_terminal_text("safe\ntext\t\x07") == "safe\ntext\t�"
    assert "No Memory changes have been applied." in snapshot


def test_review_session_round_trip_and_full_context_staleness():
    ctx, report, _, _ = _context_and_report()
    session = create_ambiguity_review(ctx, report)

    restored = ReviewSession.from_dict(session.to_dict())
    assert restored.to_dict() == session.to_dict()
    assert review_matches_context(restored, ctx)

    unrelated_direct = next(
        item
        for item in ctx.iter_items()
        if isinstance(item, Memory) and item.uid not in {
            finding.memory.uid for finding in report.findings
        }
    )
    unrelated_direct.content = "프레임 안의 다른 Memory가 변경되었다."
    assert not review_matches_context(restored, ctx)

    with pytest.raises(ReviewError, match="schema version"):
        ReviewSession.from_dict(
            {**session.to_dict(), "schema_version": 999}
        )

    reordered, reordered_report, _, _ = _context_and_report()
    reordered_session = create_ambiguity_review(reordered, reordered_report)
    reordered.order = list(reversed(reordered.order))
    assert not review_matches_context(reordered_session, reordered)

    recreated = ops.init(reordered.name)
    for item in reordered.iter_items():
        if isinstance(item, Memory):
            ops.add(recreated, item.content)
    assert not review_matches_context(reordered_session, recreated)


def test_store_rejects_duplicate_json_keys_in_review_session(isolated_store):
    MemoryStore()
    (isolated_store / "review-session.json").write_text(
        '{"uid": "one", "uid": "two"}'
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        MemoryStore().load_review_session()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("kind", []),
        ("sort_mode", []),
        ("cursor_uid", []),
    ],
)
def test_store_wraps_malformed_json_types_as_review_errors(
    isolated_store,
    field,
    invalid,
):
    ctx, report, _, _ = _context_and_report()
    data = create_ambiguity_review(ctx, report).to_dict()
    data[field] = invalid
    MemoryStore()
    (isolated_store / "review-session.json").write_text(json.dumps(data))

    with pytest.raises(ValueError, match="invalid"):
        MemoryStore().load_review_session()


def test_prompt_shell_accepts_candidate_plus_korean_comment_and_right_arrow():
    ctx, report, first, third = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    saved: list[dict[str, object]] = []

    with create_pipe_input() as pipe_input:
        # Select reading 2, focus the only response field, type a refinement,
        # save-and-next, then quit from the second issue.
        pipe_input.send_text("2\r추가로 교직원만 출입할 수 있다.\x13q")
        result = run_review_shell(
            session,
            ctx,
            save=lambda value: saved.append(value.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    first_response = result.response_for(first.uid)
    assert first_response.selected_choice_uid.endswith(":reading:2")
    assert first_response.text == "추가로 교직원만 출입할 수 있다."
    assert result.cursor_uid == third.uid
    assert saved

    second_session = create_ambiguity_review(ctx, report)
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[Cq")
        run_review_shell(
            second_session,
            ctx,
            save=lambda value: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )
    assert second_session.cursor_uid == third.uid


def test_prompt_shell_escape_closes_from_the_root_review_surface():
    ctx, report, _, _ = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    saved: list[dict[str, object]] = []

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b")
        result = run_review_shell(
            session,
            ctx,
            save=lambda value: saved.append(value.to_dict()),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert result is session
    assert saved


def test_prompt_shell_rejects_oversized_response_without_silent_truncation(
    monkeypatch,
):
    ctx, report, first, third = _context_and_report()
    session = create_ambiguity_review(ctx, report)
    monkeypatch.setattr(
        "memcommit.commands.review_shell.REVIEW_RESPONSE_CHAR_LIMIT",
        5,
    )

    with create_pipe_input() as pipe_input:
        # The first save is rejected at six characters. The reviewer removes
        # one character and explicitly saves the complete five-character text.
        pipe_input.send_text("\r123456\x13\x7f\x13q")
        run_review_shell(
            session,
            ctx,
            save=lambda value: None,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert session.response_for(first.uid).text == "12345"
    assert session.cursor_uid == third.uid


def test_cli_creates_snapshot_resumes_without_provider_and_never_mutates(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("review/context")
    first = ops.add(ctx, "같은 NFC를 쓴다.")
    ops.add(ctx, "직원 출입구는 계속 열린다.")
    store.save(ctx)
    store.set_current(ctx.name)
    context_path = store._context_file(ctx.name)
    context_before = context_path.read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    def respond(payload):
        ids = {
            memory["content"]: memory["candidate_id"]
            for memory in payload["memories"]
        }
        return {
            "findings": [
                {
                    "candidate_id": ids[first.content],
                    "interpretation": "COMPETING",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "It means the same NFC mechanism.",
                        "It means the same credential policy.",
                    ],
                    "reason": (
                        "“same NFC” has competing readings, so the accepted "
                        "credential cannot be determined reliably."
                    ),
                    "question": "Which NFC relationship is intended?",
                }
            ]
        }

    provider = PayloadProvider(respond)
    monkeypatch.setattr(
        "memcommit.commands.review.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    created = runner.invoke(
        app,
        ["review", "ambiguities", "--snapshot"],
    )
    assert created.exit_code == 0, created.output
    assert "COMPETING · REQUIRED" in created.output
    assert created.output.count(RESPONSE_LABEL) == 1
    assert len(provider.calls) == 1

    review_path = isolated_store / "review-session.json"
    review_before = review_path.read_bytes()
    monkeypatch.setattr(
        "memcommit.commands.review.connect_codex_chatgpt_provider",
        lambda: pytest.fail("replacement guard must run before provider"),
    )
    refused = runner.invoke(
        app,
        ["review", "ambiguities", "--snapshot"],
    )
    assert refused.exit_code == 1
    assert "--replace-review" in refused.output
    assert review_path.read_bytes() == review_before

    monkeypatch.setattr(
        "memcommit.commands.review.connect_codex_chatgpt_provider",
        lambda: pytest.fail("resume must not reconnect"),
    )
    resumed = runner.invoke(app, ["review", "--snapshot"])
    assert resumed.exit_code == 0
    assert "same NFC mechanism" in resumed.output
    assert context_path.read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before


def test_cli_refuses_stale_saved_review(isolated_store, monkeypatch):
    store = MemoryStore()
    ctx = ops.init("review/context")
    memory = ops.add(ctx, "Ask the coordinator.")
    store.save(ctx)
    store.set_current(ctx.name)
    provider = PayloadProvider(
        lambda payload: {
            "findings": [
                {
                    "candidate_id": payload["memories"][0]["candidate_id"],
                    "interpretation": "SINGLE",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "Ask the responsible coordinator.",
                    ],
                    "reason": (
                        "The responsible coordinator has one reading, but "
                        "clarification is required because no contact route "
                        "can be determined."
                    ),
                    "question": "How can the coordinator be contacted?",
                }
            ]
        }
    )
    monkeypatch.setattr(
        "memcommit.commands.review.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(
        app,
        ["review", "ambiguities", "--snapshot"],
    ).exit_code == 0

    changed = store.load_direct(ctx.name)
    changed.replace(Memory(uid=memory.uid, content="Changed."))
    store.save(changed)

    stale = runner.invoke(app, ["review", "--snapshot"])
    assert stale.exit_code == 1
    assert "stale" in stale.output


def test_explicit_replace_recovers_from_a_corrupt_saved_review(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("review/context")
    ops.add(ctx, "A complete Memory.")
    store.save(ctx)
    store.set_current(ctx.name)
    (isolated_store / "review-session.json").write_text("{invalid")
    provider = PayloadProvider(lambda payload: {"findings": []})
    monkeypatch.setattr(
        "memcommit.commands.review.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "review",
            "ambiguities",
            "--replace-review",
            "--snapshot",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "no actionable ambiguity findings" in result.output
    assert len(provider.calls) == 1
    assert store.load_review_session() is not None
