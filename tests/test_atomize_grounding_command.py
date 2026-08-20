"""CLI, persistence, application, and provenance for atomize grounding."""
from __future__ import annotations

import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.atomize import (
    ATOMIZE_RULESET_VERSION,
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeQualityIssue,
    AtomizeReading,
)
from memcommit.atomize_grounding_provider import (
    ATOMIZE_GROUNDING_PAYLOAD_MARKER,
)
from memcommit.atomize_workbench import create_atomize_workbench
from memcommit.cli import app
from memcommit.context import AutoCheckpoint, Memory, MemoryRef
from memcommit.provenance import build_trace
from memcommit.rationale import build_rationale
from memcommit.review import direct_context_digest
from memcommit.store import MemoryStore


runner = CliRunner()
GROUNDING_SCREEN_CAPTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "examples"
    / "mem-atomize-grounding-screens"
)


def _assert_grounding_screen_capture(
    filename: str,
    output: str,
    replacements: dict[str, str],
) -> None:
    normalized = output.replace("\r\n", "\n")
    normalized = "\n".join(
        line.rstrip() for line in normalized.splitlines()
    ) + ("\n" if normalized.endswith("\n") else "")
    for actual, stable in replacements.items():
        normalized = normalized.replace(actual, stable)
    expected = (GROUNDING_SCREEN_CAPTURE_DIR / filename).read_text(
        encoding="utf-8"
    )
    assert normalized == expected


def _saved_analysis(store: MemoryStore):
    ctx = ops.init("temp/grounding")
    student = ops.add(
        ctx,
        "Students should be guided to use a physical card or the app.",
    )
    staff = ops.add(ctx, "The staff-only entrance uses the same NFC.")
    store.save(
        ctx,
        AutoCheckpoint(
            command="init",
            args={"name": ctx.name},
            description=f"Initialized context '{ctx.name}'",
        ),
    )
    store.set_current(ctx.name)
    items = tuple(
        AtomizeAnalysisItem(
            memory_uid=memory.uid,
            content=memory.content,
            position=position,
            classification="UNCERTAIN",
            reason_codes=("A06_NO_HIDDEN_CONTEXT",),
            children=(),
            reason="The source needs a local authentication reading.",
            lint=(),
        )
        for position, memory in enumerate((student, staff))
    )
    issues = (
        AtomizeQualityIssue(
            uid="ambiguity:student-auth",
            kind="AMBIGUITY",
            source_uids=(student.uid,),
            reason=(
                "The note permits physical-card or app guidance, but the "
                "accepted Main Building method is unclear."
            ),
            question="Does the Main Building accept the app?",
            interpretation="COMPETING",
            clarification="REQUIRED",
            conflict=None,
            readings=(
                AtomizeReading(
                    uid="reading:student:card",
                    role="COMPETING",
                    label="Physical card only",
                    text="Students must use a physical NFC card.",
                ),
                AtomizeReading(
                    uid="reading:student:app",
                    role="COMPETING",
                    label="Physical card or app",
                    text="Students may use a physical card or the app.",
                ),
            ),
            scope_dimensions=(),
        ),
        AtomizeQualityIssue(
            uid="ambiguity:staff-same-nfc",
            kind="AMBIGUITY",
            source_uids=(staff.uid,),
            reason=(
                "The phrase 'same NFC' does not say whether the staff-only "
                "entrance inherits the physical-card-only exception."
            ),
            question="Which NFC rule applies to the staff-only entrance?",
            interpretation="DOMINANT",
            clarification="REQUIRED",
            conflict=None,
            readings=(
                AtomizeReading(
                    uid="reading:staff:physical",
                    role="DOMINANT",
                    label="Same physical card",
                    text="The staff-only entrance uses the physical NFC card.",
                ),
                AtomizeReading(
                    uid="reading:staff:generic",
                    role="ALTERNATIVE",
                    label="Same generic NFC",
                    text="The staff-only entrance uses an unspecified NFC method.",
                ),
            ),
            scope_dimensions=(),
        ),
    )
    analysis = AtomizeAnalysisSession(
        uid=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
        context_uid=ctx.uid,
        context_name=ctx.name,
        context_digest=direct_context_digest(ctx),
        ruleset_version=ATOMIZE_RULESET_VERSION,
        memory_count=2,
        projected_memory_count=2,
        items=items,
        overview=AtomizeOverview(
            understood=AtomizeOverviewSection(
                text="The notes describe student and staff NFC access.",
                source_uids=(student.uid, staff.uid),
            ),
            changed=AtomizeOverviewSection(
                text="No source has yet been rewritten.",
                source_uids=(student.uid, staff.uid),
            ),
            unresolved=AtomizeOverviewSection(
                text="The accepted NFC method remains unclear.",
                source_uids=(student.uid, staff.uid),
            ),
        ),
        quality_issues=issues,
    )
    analysis = AtomizeAnalysisSession.from_dict(analysis.to_dict())
    store.save_atomize_analysis(analysis)
    store.save_atomize_workbench(create_atomize_workbench(analysis))
    return ctx, student, staff, analysis


class TwoTurnGroundingProvider:
    def __init__(self):
        self.calls = 0
        self.payloads = []

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "atomize_grounding_turn"
        self.calls += 1
        payload = json.loads(
            prompt.split(ATOMIZE_GROUNDING_PAYLOAD_MARKER, 1)[1]
        )
        self.payloads.append(payload)
        anchor = payload["anchor"]["issue_id"]
        memories = {
            memory["content"]: memory
            for memory in payload["context"]["memories"]
        }
        student = memories[
            "Students should be guided to use a physical card or the app."
        ]
        staff = memories["The staff-only entrance uses the same NFC."]
        other = next(
            issue["issue_id"]
            for issue in payload["actionable_issues"]
            if (
                issue["issue_id"] != anchor
                and issue["kind"] == "AMBIGUITY"
                and issue["source_memory_ids"] == [staff["memory_id"]]
            )
        )
        latest_turn = payload["turns"][-1]["turn_id"]

        if self.calls == 1:
            return json.dumps(
                {
                    "active_understanding": [
                        "The Main Building accepts only a physical NFC card.",
                        "Students must not be guided to use the app there.",
                    ],
                    "answered_prior_question_ids": [],
                    "direct": {
                        "status": "RESOLVED",
                        "explanation": (
                            "The selected student-authentication reading "
                            "appears resolved as physical-card-only."
                        ),
                        "proposal_keys": ["edit-student"],
                        "question_keys": [],
                    },
                    "downstream": [
                        {
                            "issue_id": other,
                            "effect": "NEEDS_CONFIRMATION",
                            "explanation": (
                                "The phrase 'same NFC' may extend the physical "
                                "card rule to the staff-only entrance."
                            ),
                            "proposal_keys": [],
                            "question_keys": ["staff-scope"],
                        }
                    ],
                    "follow_ups": [
                        {
                            "question_key": "staff-scope",
                            "kind": "SCOPE_CHECK",
                            "priority": "REQUIRED",
                            "text": (
                                "Does the staff-only entrance also reject the "
                                "app and require the physical NFC card?"
                            ),
                            "reason": (
                                "Without this answer, 'same NFC' cannot be "
                                "rewritten as a stand-alone staff rule."
                            ),
                            "issue_ids": [other],
                        }
                    ],
                    "edits": [
                        {
                            "proposal_key": "edit-student",
                            "necessity": "REQUIRED",
                            "target_memory_id": student["memory_id"],
                            "expected_content_digest": student[
                                "content_digest"
                            ],
                            "content": (
                                "Students must be guided to use a physical "
                                "NFC card at the Main Building entrance; app "
                                "authentication is not accepted there."
                            ),
                            "reason": (
                                "Remove app guidance under the user's "
                                "physical-card-only clarification."
                            ),
                            "issue_ids": [anchor],
                            "grounded_by_turn_ids": [latest_turn],
                        }
                    ],
                    "additions": [],
                    "ready_to_apply": False,
                }
            )

        return json.dumps(
            {
                "active_understanding": [
                    "The Main Building accepts only a physical NFC card.",
                    "Students must not be guided to use the app there.",
                    (
                        "The staff-only entrance uses the same "
                        "physical-card-only method."
                    ),
                ],
                "answered_prior_question_ids": [
                    payload["previous_assessment"]["follow_ups"][0][
                        "question_id"
                    ]
                ],
                "direct": {
                    "status": "RESOLVED",
                    "explanation": (
                        "The selected student-authentication issue remains "
                        "resolved under the corrected shared understanding."
                    ),
                    "proposal_keys": ["edit-student"],
                    "question_keys": [],
                },
                "downstream": [
                    {
                        "issue_id": other,
                        "effect": "REQUIRES_CHANGE",
                        "explanation": (
                            "The staff Memory must name the inherited "
                            "physical-card-only rule explicitly."
                        ),
                        "proposal_keys": ["edit-staff"],
                        "question_keys": [],
                    }
                ],
                "follow_ups": [],
                "edits": [
                    {
                        "proposal_key": "edit-student",
                        "necessity": "REQUIRED",
                        "target_memory_id": student["memory_id"],
                        "expected_content_digest": student["content_digest"],
                        "content": (
                            "Students must be guided to use a physical NFC "
                            "card at the Main Building entrance; app "
                            "authentication is not accepted there."
                        ),
                        "reason": (
                            "Remove the contradicted app guidance under the "
                            "confirmed Main Building exception."
                        ),
                        "issue_ids": [anchor],
                        "grounded_by_turn_ids": [
                            turn["turn_id"] for turn in payload["turns"]
                        ],
                    },
                    {
                        "proposal_key": "edit-staff",
                        "necessity": "REQUIRED",
                        "target_memory_id": staff["memory_id"],
                        "expected_content_digest": staff["content_digest"],
                        "content": (
                            "The staff-only entrance requires the same "
                            "physical NFC card and does not accept app "
                            "authentication."
                        ),
                        "reason": (
                            "Make the user's confirmed scope extension "
                            "source-locally explicit."
                        ),
                        "issue_ids": [other],
                        "grounded_by_turn_ids": [latest_turn],
                    },
                ],
                "additions": [],
                "ready_to_apply": True,
            }
        )


def test_cli_grounding_dialogue_resumes_then_applies_once_with_provenance(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, student, staff, analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    context_before = store._context_file(ctx.name).read_bytes()
    context_names_before = store.list_context_names()
    checkpoints_before = len(store.list_checkpoints(ctx.name))
    frame_replacements = {
        analysis.uid[:8]: "<ANALYSIS>",
        student.uid[:8]: "<STUDENT>",
        staff.uid[:8]: "<STAFF>",
    }

    # Bare Atomize now applies the current Context immediately. Grounding is
    # an explicit advanced review route, so name the Context when opening its
    # existing workbench before starting the dialogue.
    workbench_screen = runner.invoke(
        app,
        ["atomize", "--context", ctx.name],
    )

    assert workbench_screen.exit_code == 0, workbench_screen.output
    assert provider.calls == 0
    _assert_grounding_screen_capture(
        "00-workbench.txt",
        workbench_screen.output,
        frame_replacements,
    )

    evaluated = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            (
                "The Main Building entrance accepts only a physical NFC "
                "card; the app does not work there."
            ),
        ],
    )

    assert evaluated.exit_code == 0, evaluated.output
    assert "CURRENT · RESOLVED" in evaluated.output
    assert "[FOLLOW-UP]" in evaluated.output
    assert "staff-only entrance" in evaluated.output
    assert "PROVISIONAL CHANGES" in evaluated.output
    assert "READY TO CHANGE" not in evaluated.output
    assert provider.calls == 1
    assert store.list_context_names() == context_names_before
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before
    opened_grounding = store.load_atomize_grounding_session(ctx.uid)
    assert opened_grounding is not None
    screen_replacements = {
        **frame_replacements,
        opened_grounding.uid[:8]: "<SESSION>",
    }
    _assert_grounding_screen_capture(
        "01-evaluate-awaiting-reply.txt",
        evaluated.output,
        screen_replacements,
    )

    resumed = runner.invoke(app, ["atomize"])
    assert resumed.exit_code == 0, resumed.output
    assert "Resumed without calling the semantic provider." in resumed.output
    assert provider.calls == 1
    assert store.list_context_names() == context_names_before
    _assert_grounding_screen_capture(
        "02-provider-free-resume.txt",
        resumed.output,
        screen_replacements,
    )

    replied = runner.invoke(
        app,
        [
            "atomize",
            "--reply",
            (
                "Correct: do not tell students to use the app. The "
                "staff-only entrance uses the same physical-card-only method."
            ),
            "--revision",
            "correct",
        ],
    )
    assert replied.exit_code == 0, replied.output
    assert "READY_TO_APPLY" in replied.output
    assert "READY TO CHANGE" in replied.output
    assert provider.calls == 2
    grounded = store.load_atomize_grounding_session(ctx.uid)
    assert grounded is not None
    first_turn, second_turn = grounded.turns
    assert second_turn.answers_question_uids == (
        first_turn.assessment.follow_ups[0].uid,
    )
    assert second_turn.revises_turn_uids == (first_turn.uid,)
    assert store.list_context_names() == context_names_before
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before
    _assert_grounding_screen_capture(
        "03-reply-ready-to-apply.txt",
        replied.output,
        screen_replacements,
    )

    ready_resumed = runner.invoke(app, ["atomize"])
    assert ready_resumed.exit_code == 0, ready_resumed.output
    assert provider.calls == 2
    _assert_grounding_screen_capture(
        "04-provider-free-ready-resume.txt",
        ready_resumed.output,
        screen_replacements,
    )

    applied = runner.invoke(app, ["atomize", "--accept-grounding"])
    assert applied.exit_code == 0, applied.output
    assert "Applied 2 grounded changes" in applied.output
    assert store.list_context_names() == context_names_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before + 1
    checkpoint_grounding = next(
        checkpoint["args"]["grounding"]
        for checkpoint in store.list_checkpoints(ctx.name)
        if checkpoint.get("command") == "atomize-grounding"
    )
    assert checkpoint_grounding["turns"][1][
        "answers_question_uids"
    ] == [first_turn.assessment.follow_ups[0].uid]
    assert checkpoint_grounding["turns"][1]["revises_turn_uids"] == [
        first_turn.uid
    ]
    assert checkpoint_grounding["turns"][1]["assessment"]["downstream"][0][
        "effect"
    ] == "REQUIRES_CHANGE"
    assert all(
        decision["action"] == "ACCEPT"
        for decision in checkpoint_grounding["decisions"]
    )
    updated = store.load_direct(ctx.name)
    assert isinstance(updated.memories[student.uid], Memory)
    assert "app authentication is not accepted" in (
        updated.memories[student.uid].content
    )
    assert isinstance(updated.memories[staff.uid], Memory)
    assert "same physical NFC card" in updated.memories[staff.uid].content
    applied_grounding = store.load_atomize_grounding_session(ctx.uid)
    assert applied_grounding is not None
    assert applied_grounding.application is not None
    applied_replacements = {
        **screen_replacements,
        applied_grounding.application.checkpoint_uid[:8]: "<CHECKPOINT>",
    }
    _assert_grounding_screen_capture(
        "05-applied.txt",
        applied.output,
        applied_replacements,
    )

    repeated = runner.invoke(app, ["atomize", "--accept-grounding"])
    assert repeated.exit_code == 0, repeated.output
    assert "no duplicate checkpoint" in repeated.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before + 1

    trace = build_trace(store, updated, student.uid)
    grounded_event = next(
        event
        for event in trace.events
        if event.command == "atomize-grounding"
    )
    assert grounded_event.kind == "EDITED"
    assert grounded_event.evidence == "RECORDED"
    assert grounded_event.reason_codes == ("ATOMIZE_GROUNDING",)
    assert "Remove the contradicted app guidance" in grounded_event.reason
    assert grounded_event.declared_frame is not None
    assert "Main Building entrance accepts only" in (
        grounded_event.declared_frame
    )
    rationale = build_rationale(store, updated, trace, None)
    assert grounded_event in rationale.recorded_reason_events

    undone = runner.invoke(app, ["undo"])
    assert undone.exit_code == 0, undone.output
    assert [
        memory.content for memory in store.load_direct(ctx.name).memories.values()
    ] == [
        "Students should be guided to use a physical card or the app.",
        "The staff-only entrance uses the same NFC.",
    ]
    undone_grounding = store.load_atomize_grounding_session(ctx.uid)
    assert undone_grounding.state == "READY_TO_APPLY"
    assert undone_grounding.application is None

    redone = runner.invoke(app, ["redo"])
    assert redone.exit_code == 0, redone.output
    redone_grounding = store.load_atomize_grounding_session(ctx.uid)
    assert redone_grounding.state == "APPLIED"
    assert redone_grounding.application is not None
    assert [
        entry["command"] for entry in store.list_checkpoints(ctx.name)[:3]
    ] == ["redo", "undo", "atomize-grounding"]
    assert "app authentication is not accepted" in (
        store.load_direct(ctx.name).memories[student.uid].content
    )


def test_grounding_carries_selected_reading_and_free_text_into_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _student, _staff, analysis = _saved_analysis(store)
    workbench = store.load_atomize_workbench(analysis)
    assert workbench is not None
    response = workbench.response_for(analysis.quality_issues[0].uid)
    response.selected_choice_uid = (
        analysis.quality_issues[0].readings[0].uid
    )
    response.text = "This exception applies only to the Main Building."
    store.save_atomize_workbench(workbench)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    evaluated = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Use that selected reading in this grounding round.",
        ],
    )

    assert evaluated.exit_code == 0, evaluated.output
    saved_evidence = provider.payloads[0]["anchor"][
        "saved_workbench_response"
    ]
    assert saved_evidence["selected_reading_id"].endswith(".r01")
    assert saved_evidence["text"] == response.text
    assert "SAVED WORKBENCH EVIDENCE" in evaluated.output
    assert "Physical card only" in evaluated.output
    grounding = store.load_atomize_grounding_session(ctx.uid)
    assert grounding is not None
    assert grounding.anchor.selected_reading_uid == (
        response.selected_choice_uid
    )
    assert grounding.anchor.workbench_response == response.text
    replied = runner.invoke(
        app,
        [
            "atomize",
            "--reply",
            (
                "The staff-only entrance also uses the same "
                "physical-card-only method."
            ),
        ],
    )
    assert replied.exit_code == 0, replied.output
    applied = runner.invoke(app, ["atomize", "--accept-grounding"])
    assert applied.exit_code == 0, applied.output
    updated = store.load_direct(ctx.name)
    trace = build_trace(store, updated, _student.uid)
    event = next(
        item
        for item in trace.events
        if item.command == "atomize-grounding"
    )
    assert event.declared_frame is not None
    assert "Saved workbench selected reading:" in event.declared_frame
    assert (
        analysis.quality_issues[0].readings[0].text
        in event.declared_frame
    )
    assert "Saved workbench response:" in event.declared_frame
    assert response.text in event.declared_frame

    checkpoint = next(
        item
        for item in store.list_checkpoints(ctx.name)
        if item.get("command") == "atomize-grounding"
    )
    checkpoint_path = next(
        store._checkpoints_dir(ctx.name).glob(
            f"*-{checkpoint['uid'][:8]}.json"
        )
    )
    tampered = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    tampered["args"]["grounding"]["turns"][0]["revision"] = "EXTEND"
    checkpoint_path.write_text(json.dumps(tampered), encoding="utf-8")
    reconstructed = build_trace(store, updated, _student.uid)
    reconstructed_event = next(
        item
        for item in reconstructed.events
        if item.command == "atomize-grounding"
    )
    assert reconstructed_event.evidence == "RECONSTRUCTED"
    assert any(
        "invalid grounding session or change set" in warning
        for warning in reconstructed.warnings
    )

    tampered["args"]["grounding"]["turns"][0]["revision"] = "INITIAL"
    tampered["args"]["grounding"]["schema_version"] = True
    checkpoint_path.write_text(json.dumps(tampered), encoding="utf-8")
    boolean_version = build_trace(store, updated, _student.uid)
    boolean_version_event = next(
        item
        for item in boolean_version.events
        if item.command == "atomize-grounding"
    )
    assert boolean_version_event.evidence == "RECONSTRUCTED"
    assert any(
        "unsupported grounding record" in warning
        for warning in boolean_version.warnings
    )


def test_cli_keep_review_only_creates_no_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _student, _staff, _analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    context_names_before = store.list_context_names()
    context_before = store._context_file(ctx.name).read_bytes()

    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )
    kept = runner.invoke(app, ["atomize", "--keep-review-only"])

    assert opened.exit_code == 0, opened.output
    assert kept.exit_code == 0, kept.output
    assert "KEPT_REVIEW_ONLY" in kept.output
    assert "REVIEW-ONLY PROPOSALS — not applied" in kept.output
    assert "PROVISIONAL CHANGES" not in kept.output
    assert "No Memory changes or checkpoint" in kept.output
    assert store.list_context_names() == context_names_before
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count
    kept_session = store.load_atomize_grounding_session(ctx.uid)
    assert kept_session is not None
    history = store.load_atomize_grounding_history(ctx.uid)
    assert [session.uid for session in history] == [kept_session.uid]
    assert history[0].turns[0].comment == (
        "Only a physical NFC card works at this entrance."
    )

    next_provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: next_provider,
    )
    reopened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Reconsider the same issue in a separate review round.",
        ],
    )
    assert reopened.exit_code == 0, reopened.output
    current = store.load_atomize_grounding_session(ctx.uid)
    assert current is not None
    assert current.uid != kept_session.uid
    assert [
        session.uid
        for session in store.load_atomize_grounding_history(ctx.uid)
    ] == [kept_session.uid]


@pytest.mark.parametrize(
    "apply_args",
    [
        ["--save"],
        ["--save-as", "temp/blocked-save-as"],
    ],
)
def test_open_grounding_explicitly_blocks_ordinary_atomize_save_modes(
    isolated_store,
    monkeypatch,
    apply_args,
):
    store = MemoryStore()
    ctx, _student, _staff, _analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )
    assert opened.exit_code == 0, opened.output
    context_before = store._context_file(ctx.name).read_bytes()
    checkpoints_before = len(store.list_checkpoints(ctx.name))

    blocked = runner.invoke(app, ["atomize", *apply_args])

    assert blocked.exit_code == 1
    assert "grounding dialogue is still open" in blocked.output
    assert "Resumed without calling" not in blocked.output
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoints_before
    assert not store.context_exists("temp/blocked-save-as")


def test_accept_retry_recovers_checkpoint_after_receipt_save_failure(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _student, _staff, _analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    ).exit_code == 0
    assert runner.invoke(
        app,
        [
            "atomize",
            "--reply",
            "The staff-only entrance uses the same physical card.",
        ],
    ).exit_code == 0
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    original_save_session = MemoryStore.save_atomize_grounding_session

    def fail_application_receipt(self, session):
        if session.state == "APPLIED":
            raise OSError("simulated receipt write failure")
        return original_save_session(self, session)

    monkeypatch.setattr(
        MemoryStore,
        "save_atomize_grounding_session",
        fail_application_receipt,
    )
    failed = runner.invoke(app, ["atomize", "--accept-grounding"])

    assert failed.exit_code == 1
    assert "simulated receipt write failure" in failed.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1
    persisted = store.load_atomize_grounding_session(ctx.uid)
    assert persisted is not None
    assert persisted.state == "READY_TO_APPLY"

    checkpoint = next(
        item
        for item in store.list_checkpoints(ctx.name)
        if item.get("command") == "atomize-grounding"
    )
    checkpoint_path = next(
        store._checkpoints_dir(ctx.name).glob(
            f"*-{checkpoint['uid'][:8]}.json"
        )
    )
    checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint_data["command"] = "edit"
    checkpoint_path.write_text(
        json.dumps(checkpoint_data),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        MemoryStore,
        "save_atomize_grounding_session",
        original_save_session,
    )
    false_authority = runner.invoke(
        app,
        ["atomize", "--accept-grounding"],
    )
    assert false_authority.exit_code == 1
    assert "changed" in false_authority.output.casefold()
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1

    checkpoint_data["command"] = "atomize-grounding"
    checkpoint_path.write_text(
        json.dumps(checkpoint_data),
        encoding="utf-8",
    )
    recovered = runner.invoke(app, ["atomize", "--accept-grounding"])

    assert recovered.exit_code == 0, recovered.output
    assert "prior application was recovered" in recovered.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1
    persisted = store.load_atomize_grounding_session(ctx.uid)
    assert persisted is not None
    assert persisted.state == "APPLIED"
    assert checkpoint_data["args"]["grounding"]["decisions"] == [
        decision.to_dict() for decision in persisted.decisions
    ]


def test_accept_retry_recovers_when_terminal_archive_precedes_latest_receipt(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _student, _staff, _analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    assert runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    ).exit_code == 0
    assert runner.invoke(
        app,
        [
            "atomize",
            "--reply",
            "The staff-only entrance uses the same physical card.",
        ],
    ).exit_code == 0
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    latest_path = store._atomize_grounding_session_path(ctx.uid)
    from memcommit import store as store_module

    original_write = store_module._write_json_atomic
    failed_latest_receipt = False

    def fail_latest_receipt_once(path, data):
        nonlocal failed_latest_receipt
        if (
            path == latest_path
            and data.get("state") == "APPLIED"
            and not failed_latest_receipt
        ):
            failed_latest_receipt = True
            raise OSError("simulated latest-receipt write failure")
        return original_write(path, data)

    monkeypatch.setattr(
        "memcommit.store._write_json_atomic",
        fail_latest_receipt_once,
    )
    failed = runner.invoke(app, ["atomize", "--accept-grounding"])

    assert failed.exit_code == 1
    assert "simulated latest-receipt write failure" in failed.output
    assert failed_latest_receipt
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1
    persisted = store.load_atomize_grounding_session(ctx.uid)
    assert persisted is not None
    assert persisted.state == "READY_TO_APPLY"
    history = store.load_atomize_grounding_history(ctx.uid)
    assert len(history) == 1
    assert history[0].state == "APPLIED"

    monkeypatch.setattr(
        "memcommit.store._write_json_atomic",
        original_write,
    )
    recovered = runner.invoke(app, ["atomize", "--accept-grounding"])

    assert recovered.exit_code == 0, recovered.output
    assert "prior application was recovered" in recovered.output
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count + 1
    persisted = store.load_atomize_grounding_session(ctx.uid)
    assert persisted is not None
    assert persisted.state == "APPLIED"
    history = store.load_atomize_grounding_history(ctx.uid)
    assert len(history) == 1
    assert history[0].to_dict() == persisted.to_dict()


def test_mixed_edit_add_save_failure_leaves_no_partial_context_or_checkpoint(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, student, _staff, _analysis = _saved_analysis(store)

    class ReadyEditAddProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "atomize_grounding_turn"
            payload = json.loads(
                prompt.split(ATOMIZE_GROUNDING_PAYLOAD_MARKER, 1)[1]
            )
            anchor = payload["anchor"]["issue_id"]
            latest_turn = payload["turns"][-1]["turn_id"]
            source = next(
                memory
                for memory in payload["context"]["memories"]
                if memory["content"].startswith("Students should")
            )
            return json.dumps(
                {
                    "active_understanding": [
                        "Students must use a physical NFC card."
                    ],
                    "answered_prior_question_ids": [],
                    "direct": {
                        "status": "RESOLVED",
                        "explanation": "The credential method is explicit.",
                        "proposal_keys": ["edit-source", "add-rule"],
                        "question_keys": [],
                    },
                    "downstream": [],
                    "follow_ups": [],
                    "edits": [
                        {
                            "proposal_key": "edit-source",
                            "necessity": "REQUIRED",
                            "target_memory_id": source["memory_id"],
                            "expected_content_digest": source[
                                "content_digest"
                            ],
                            "content": (
                                "Students must use a physical NFC card; app "
                                "authentication is not accepted."
                            ),
                            "reason": "Remove the disallowed app alternative.",
                            "issue_ids": [anchor],
                            "grounded_by_turn_ids": [latest_turn],
                        }
                    ],
                    "additions": [
                        {
                            "proposal_key": "add-rule",
                            "necessity": "REQUIRED",
                            "content": (
                                "The entrance credential policy is "
                                "physical-card-only."
                            ),
                            "position": 1,
                            "reason": (
                                "Retain a stand-alone rule for dependent "
                                "access notes."
                            ),
                            "issue_ids": [anchor],
                            "grounded_by_turn_ids": [latest_turn],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        ReadyEditAddProvider,
    )
    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only the physical NFC card is accepted.",
        ],
    )
    assert opened.exit_code == 0, opened.output
    context_before = store._context_file(ctx.name).read_bytes()
    checkpoint_count = len(store.list_checkpoints(ctx.name))
    original_write = store_module._write_json_atomic

    def fail_context_write(path, data):
        if path == store._context_file(ctx.name):
            raise OSError("simulated mixed application failure")
        return original_write(path, data)

    monkeypatch.setattr(
        store_module,
        "_write_json_atomic",
        fail_context_write,
    )
    failed = runner.invoke(app, ["atomize", "--accept-grounding"])

    assert failed.exit_code == 1
    assert "simulated mixed application failure" in failed.output
    assert store._context_file(ctx.name).read_bytes() == context_before
    assert len(store.list_checkpoints(ctx.name)) == checkpoint_count
    unchanged = store.load_direct(ctx.name)
    assert isinstance(unchanged.memories[student.uid], Memory)
    assert "physical card or the app" in (
        unchanged.memories[student.uid].content
    )
    grounding = store.load_atomize_grounding_session(ctx.uid)
    assert grounding is not None
    assert grounding.state == "READY_TO_APPLY"


def test_cli_reply_fails_closed_when_context_changed(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, student, _staff, _analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )
    assert opened.exit_code == 0, opened.output

    changed = store.load_for_update(ctx.name)
    memory = changed.memories[student.uid]
    assert isinstance(memory, Memory)
    memory.content = "Externally changed content."
    store.save(
        changed,
        AutoCheckpoint(
            command="edit",
            args={"uid": student.uid, "content": memory.content},
            description="External edit",
        ),
    )
    calls_before = provider.calls

    replied = runner.invoke(
        app,
        ["atomize", "--reply", "The staff door uses the same card."],
    )

    assert replied.exit_code == 1
    assert "Saved atomize analysis is stale" in replied.output
    assert provider.calls == calls_before


def test_provider_result_is_discarded_when_workbench_changes_during_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, _student, _staff, analysis = _saved_analysis(store)
    inner = TwoTurnGroundingProvider()

    class ConcurrentWorkbenchProvider:
        def complete(self, prompt, *, operation, output_schema=None):
            raw = inner.complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
            workbench = store.load_atomize_workbench(analysis)
            assert workbench is not None
            workbench.response_for(
                analysis.quality_issues[0].uid
            ).text = "Concurrent local evidence."
            store.save_atomize_workbench(workbench)
            return raw

    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        ConcurrentWorkbenchProvider,
    )

    result = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )

    assert result.exit_code == 1
    assert "stale" in result.output.casefold()
    assert inner.calls == 1
    assert store.load_atomize_grounding_session(ctx.uid) is None


@pytest.mark.parametrize("stale_binding", ["workbench", "analysis", "context"])
def test_cli_bare_resume_fails_closed_when_grounding_binding_is_stale(
    isolated_store,
    monkeypatch,
    stale_binding,
):
    store = MemoryStore()
    ctx, student, _staff, analysis = _saved_analysis(store)
    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )
    assert opened.exit_code == 0, opened.output

    if stale_binding == "workbench":
        workbench = store.load_atomize_workbench(analysis)
        assert workbench is not None
        workbench.response_for(
            analysis.quality_issues[0].uid
        ).text = "A later workbench response changes the evidence frame."
        store.save_atomize_workbench(workbench)
    elif stale_binding == "analysis":
        replacement = replace(
            analysis,
            uid=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.save_atomize_analysis(replacement)
        store.save_atomize_workbench(create_atomize_workbench(replacement))
    else:
        changed = store.load_for_update(ctx.name)
        memory = changed.memories[student.uid]
        assert isinstance(memory, Memory)
        memory.content = "Externally changed content."
        store.save(
            changed,
            AutoCheckpoint(
                command="edit",
                args={"uid": student.uid, "content": memory.content},
                description="External edit",
            ),
        )

    calls_before = provider.calls
    resumed = runner.invoke(app, ["atomize"])

    assert resumed.exit_code == 1
    assert "Atomize error:" in resumed.output
    assert "stale" in resumed.output.casefold()
    assert "MEM ATOMIZE · GROUNDING" not in resumed.output
    assert "Resumed without calling the semantic provider." not in resumed.output
    assert provider.calls == calls_before


@pytest.mark.parametrize("reference_change", ["add", "move"])
def test_cli_grounding_stales_on_direct_memory_ref_order_change(
    isolated_store,
    monkeypatch,
    reference_change,
):
    store = MemoryStore()
    ctx, _student, _staff, _analysis = _saved_analysis(store)
    source = ops.init("temp/grounding-reference-source")
    target = ops.add(source, "Referenced source content.")
    store.save(source)
    reference = MemoryRef(
        uid=str(uuid.uuid4()),
        target_context_uid=source.uid,
        target_context_name=source.name,
        target_memory_uid=target.uid,
        target=target,
    )
    if reference_change == "move":
        initial = store.load_for_update(ctx.name)
        initial.add(reference)
        store.save(initial)

    provider = TwoTurnGroundingProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Only a physical NFC card works at this entrance.",
        ],
    )
    assert opened.exit_code == 0, opened.output
    direct_digest_before = direct_context_digest(
        store.load_direct(ctx.name)
    )

    changed = store.load_for_update(ctx.name)
    if reference_change == "add":
        changed.add(reference, position=0)
    else:
        changed.order = [
            reference.uid,
            *(
                uid
                for uid in changed.ordered_uids()
                if uid != reference.uid
            ),
        ]
    store.save(
        changed,
        AutoCheckpoint(
            command="reference-order-change",
            args={"reference_uid": reference.uid},
            description="Changed a direct MemoryRef slot",
        ),
    )

    # The semantic analysis digest intentionally covers only owned Memories;
    # the grounding binding is stricter because ADD positions use every direct
    # slot, including references.
    assert direct_context_digest(store.load_direct(ctx.name)) == (
        direct_digest_before
    )
    calls_before = provider.calls
    replied = runner.invoke(
        app,
        ["atomize", "--reply", "The staff entrance uses that same method."],
    )

    assert replied.exit_code == 1
    assert "atomize grounding session is stale" in replied.output.casefold()
    assert provider.calls == calls_before


def test_grounding_add_preserves_embedded_context_slot_and_position(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx, student, staff, _analysis = _saved_analysis(store)
    child = ops.init("temp/grounding-child")
    ops.add(child, "Child content must not be opened by direct grounding.")
    store.save(child)
    parent = store.load_for_update(ctx.name)
    parent.add(child, position=1)
    store.save(parent)

    class ReadyAddProvider:
        def __init__(self):
            self.calls = 0

        def complete(self, prompt, *, operation, output_schema=None):
            assert operation == "atomize_grounding_turn"
            self.calls += 1
            payload = json.loads(
                prompt.split(ATOMIZE_GROUNDING_PAYLOAD_MARKER, 1)[1]
            )
            anchor = payload["anchor"]["issue_id"]
            latest_turn = payload["turns"][-1]["turn_id"]
            # The direct provider view omits child contents but retains full
            # item positions: the staff Memory follows the child at slot 2.
            assert [
                memory["position"]
                for memory in payload["context"]["memories"]
            ] == [0, 2]
            return json.dumps(
                {
                    "active_understanding": [
                        "A stand-alone entrance credential rule is useful."
                    ],
                    "answered_prior_question_ids": [],
                    "direct": {
                        "status": "RESOLVED",
                        "explanation": (
                            "The reviewer supplied an explicit credential "
                            "reading for the selected issue."
                        ),
                        "proposal_keys": ["add-rule"],
                        "question_keys": [],
                    },
                    "downstream": [],
                    "follow_ups": [],
                    "edits": [],
                    "additions": [
                        {
                            "proposal_key": "add-rule",
                            "necessity": "REQUIRED",
                            "content": (
                                "The Main Building entrance accepts only a "
                                "physical NFC card."
                            ),
                            "position": 2,
                            "reason": (
                                "Preserve the grounded credential rule as a "
                                "stand-alone Memory."
                            ),
                            "issue_ids": [anchor],
                            "grounded_by_turn_ids": [latest_turn],
                        }
                    ],
                    "ready_to_apply": True,
                }
            )

    provider = ReadyAddProvider()
    monkeypatch.setattr(
        "memcommit.commands.atomize.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    opened = runner.invoke(
        app,
        [
            "atomize",
            "--evaluate",
            "1",
            "--comment",
            "Keep the physical-card-only rule as its own Memory.",
        ],
    )
    assert opened.exit_code == 0, opened.output

    def forbid_reference_resolution(*_args, **_kwargs):
        raise AssertionError(
            "grounding acceptance must not resolve referenced content"
        )

    monkeypatch.setattr(
        MemoryStore,
        "load_for_update",
        forbid_reference_resolution,
    )
    monkeypatch.setattr(
        MemoryStore,
        "load",
        forbid_reference_resolution,
    )
    monkeypatch.setattr(
        MemoryStore,
        "_load_direct_memory",
        forbid_reference_resolution,
    )
    applied = runner.invoke(app, ["atomize", "--accept-grounding"])
    assert applied.exit_code == 0, applied.output

    updated = store.load_direct(ctx.name)
    ordered = updated.ordered_uids()
    assert ordered[0] == student.uid
    assert ordered[1] == child.uid
    assert isinstance(updated.memories[ordered[1]], type(child))
    added = updated.memories[ordered[2]]
    assert isinstance(added, Memory)
    assert "physical NFC card" in added.content
    assert ordered[3] == staff.uid
    assert provider.calls == 1
