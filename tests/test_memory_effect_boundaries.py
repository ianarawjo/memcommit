"""Evidence consumption and degradation contracts across History's stage boundary."""

import ast
from pathlib import Path

import pytest

from memcommit.application.capabilities.history.reconstruction.memory_effects.derivation import (
    _transition_events,
)
from memcommit.application.capabilities.history.verification.frame import (
    _frame_from_context,
)
from memcommit.application.capabilities.history.verification.model import (
    TRACE_METADATA_LEGACY_SCHEMA_VERSION,
)
from memcommit.application.capabilities.history.verification.validators.chunk import (
    verify_context_chunk,
)
from memcommit.core.context import Context, Memory


def _frame(*items: tuple[str, str]):
    context = Context(uid="owner", name="history")
    for uid, content in items:
        context.add(Memory(uid=uid, content=content))
    return _frame_from_context(context)


def _entry(command, args):
    return {
        "uid": "checkpoint",
        "timestamp": "2026-09-05",
        "command": command,
        "description": "retained operation",
        "args": args,
    }


@pytest.mark.parametrize("valid", [True, False])
def test_explicit_relation_consumes_only_validated_source_and_result(valid):
    before = _frame(("source", "two claims"), ("edited", "old"))
    after = _frame(
        ("a", "one claim"),
        ("b", "another claim"),
        ("edited", "new"),
        ("extra", "unexplained"),
    )
    entry = _entry(
        "atomize",
        {
            "trace": {
                "schema_version": TRACE_METADATA_LEGACY_SCHEMA_VERSION,
                "changes": [
                    {
                        "kind": "SPLIT",
                        "source_uids": ["source"],
                        "result_uids": ["a", "b" if valid else "missing"],
                    }
                ],
            }
        },
    )
    events, warnings = _transition_events(before=before, after=after, entry=entry)
    if valid:
        assert [event.kind for event in events] == ["SPLIT", "EDITED", "CREATED"]
        assert events[0].evidence == "RECORDED"
        assert {state.uid for state in events[0].after} == {"a", "b"}
        assert events[-1].after[0].uid == "extra"
        assert not warnings
    else:
        assert [event.kind for event in events] == [
            "EDITED",
            "CREATED",
            "CREATED",
            "CREATED",
            "REMOVED",
        ]
        assert events[-1].before[0].uid == "source"
        assert len(warnings) == 1
        assert "does not match its snapshot" in warnings[0]


def test_atomize_invalid_later_record_retains_earlier_verified_relation():
    before = _frame(("first", "one"), ("second", "two"))
    after = _frame(("first", "one"), ("second", "changed"))
    entry = _entry(
        "atomize",
        {
            "trace": {
                "schema_version": TRACE_METADATA_LEGACY_SCHEMA_VERSION,
                "changes": [
                    {
                        "kind": "KEEP",
                        "source_uids": ["first"],
                        "result_uids": ["first"],
                    },
                    {
                        "kind": "KEEP",
                        "source_uids": ["second"],
                        "result_uids": ["second"],
                    },
                ],
            }
        },
    )
    events, warnings = _transition_events(before=before, after=after, entry=entry)
    assert [event.kind for event in events] == ["ATOMIZE_KEEP", "EDITED"]
    assert [event.evidence for event in events] == ["RECORDED", "RECONSTRUCTED"]
    assert len(warnings) == 1


@pytest.mark.parametrize("valid_second", [True, False])
def test_context_chunk_verifies_entire_split_set_before_consuming_any_uid(valid_second):
    before = _frame(("first", "one\n\ntwo"), ("second", "three\n\nfour"))
    after = _frame(
        ("a", "one"),
        ("b", "two"),
        ("c", "three"),
        ("d", "four" if valid_second else "unproven"),
    )
    entry = _entry(
        "chunk",
        {
            "method": "paragraphs",
            "splits": [
                {"uid": "first", "chunk_uids": ["a", "b"]},
                {"uid": "second", "chunk_uids": ["c", "d"]},
            ],
        },
    )
    verified = verify_context_chunk(
        before=before,
        after=after,
        entry=entry,
        removed={"first", "second"},
        added={"a", "b", "c", "d"},
    )
    events, warnings = _transition_events(before=before, after=after, entry=entry)
    if valid_second:
        assert verified is not None
        assert [event.kind for event in events] == ["SPLIT", "SPLIT"]
        assert not warnings
    else:
        assert verified is None
        assert [event.kind for event in events] == ["CREATED"] * 4 + ["REMOVED"] * 2
        assert len(warnings) == 1


def test_restoration_bypasses_relation_decoding_and_combines_affected_frame():
    before = _frame(("old", "removed"), ("stable", "before"))
    after = _frame(("new", "created"), ("stable", "after"))
    events, warnings = _transition_events(
        before=before,
        after=after,
        entry=_entry("revert", {"trace": "invalid"}),
        restoration=True,
    )
    assert len(events) == 1
    assert events[0].kind == "RESTORED"
    assert [state.uid for state in events[0].before] == ["old", "stable"]
    assert [state.uid for state in events[0].after] == ["new", "stable"]
    assert not warnings


def test_validators_do_not_construct_memory_events_or_import_effect_projectors():
    root = (
        Path(__file__).resolve().parents[1]
        / "src/memcommit/application/capabilities/history"
    )
    for path in (root / "verification/validators").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert "memory_effects" not in (node.module or ""), path
                assert "memory_event" not in (node.module or ""), path
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "MemoryHistoryEvent", path
    assert not (root / "reconstruction/memory_effect_derivation.py").exists()
