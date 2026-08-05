"""Interactive result-target selection contracts for Compare-to-Meld."""

from __future__ import annotations

import json

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

import memcommit.ops as ops
from memcommit.commands.meld import start_reviewed_symmetric_meld
from memcommit.commands.meld_target_picker import (
    choose_meld_target,
    eligible_meld_targets,
)
from memcommit.store import MemoryStore
from memcommit.comparison import ComparisonInput
from memcommit.comparison_provider import (
    COMPARISON_PAYLOAD_MARKER,
    analyze_comparison,
)
from memcommit.comparison_store import save_comparison_analysis


class _ComparisonProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        del output_schema
        assert operation == "compare_contexts"
        payload = json.loads(prompt.split(COMPARISON_PAYLOAD_MARKER, 1)[1])
        left_id = payload["frames"][0]["memories"][0]["memory_id"]
        right_id = payload["frames"][1]["memories"][0]["memory_id"]
        return json.dumps(
            {
                "overview": "The sources recommend different formats.",
                "reports": {
                    "both": "",
                    "differences": "Their preferred formats differ.",
                    "reference_only": "",
                    "compared_only": "",
                },
                "relations": [
                    {
                        "relation_key": "format",
                        "reference_memory_ids": [left_id],
                        "compared_memory_ids": [right_id],
                        "kind": "CONFLICT",
                        "status": "UNRESOLVED",
                        "summary": "Headings and transitions conflict.",
                        "reason": "One passage needs one governing format.",
                    }
                ],
                "issues": [
                    {
                        "issue_key": "format-choice",
                        "relation_keys": ["format"],
                        "priority": "REQUIRED",
                        "title": "Visible format",
                        "question": "Which format should the result use?",
                        "why_it_matters": "The result needs one readable form.",
                        "options": [
                            {"label": "Headings", "text": "Use headings."},
                            {
                                "label": "Transitions",
                                "text": "Use transitions.",
                            },
                        ],
                    }
                ],
            }
        )


def _sources(store: MemoryStore):
    left = ops.init("task-2/advisor1")
    ops.add(left, "Use headings.")
    right = ops.init("task-2/advisor2")
    ops.add(right, "Use transitions.")
    store.save(left)
    store.save(right)
    return left, right


def test_target_catalog_offers_only_empty_session_free_local_contexts(
    isolated_store,
):
    store = MemoryStore()
    left, right = _sources(store)
    empty = ops.init("task-2/result-empty")
    occupied = ops.init("task-2/result-occupied")
    ops.add(occupied, "Existing participant work.")
    store.save(empty)
    store.save(occupied)

    assert eligible_meld_targets(
        store,
        source_names=(left.name, right.name),
    ) == (empty.name,)


def test_picker_can_choose_an_existing_empty_context(isolated_store):
    store = MemoryStore()
    left, right = _sources(store)
    target = ops.init("task-2/result-empty")
    store.save(target)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b[B\r")
        receipt = choose_meld_target(
            store,
            source_names=(left.name, right.name),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.context_name == target.name
    assert receipt.create is False


def test_picker_can_validate_and_return_a_new_exact_name(isolated_store):
    store = MemoryStore()
    left, right = _sources(store)

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("nnew-study/merged-advisors\r")
        receipt = choose_meld_target(
            store,
            source_names=(left.name, right.name),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is not None
    assert receipt.context_name == "new-study/merged-advisors"
    assert receipt.create is True
    assert not store.context_exists(receipt.context_name)


def test_compare_handoff_creates_target_and_target_bound_meld_session(
    isolated_store,
):
    store = MemoryStore()
    left, right = _sources(store)
    analysis = analyze_comparison(
        ComparisonInput.from_contexts(left, right),
        _ComparisonProvider(),
    )
    save_comparison_analysis(store, analysis, expected_analysis_uid=None)

    session = start_reviewed_symmetric_meld(
        store=store,
        analysis=analysis,
        target_name="task-2/merged-advisors",
        create_target=True,
    )

    target = store.load_direct("task-2/merged-advisors")
    saved = store.load_meld_session(target.uid)
    assert saved is not None
    assert saved.uid == session.uid
    assert saved.comparison_seed is not None
    assert saved.comparison_seed.analysis.uid == analysis.uid
    assert tuple(target.iter_items()) == ()
