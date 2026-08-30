"""Contracts for read-only duplicate, ambiguity, and conflict finders."""

from __future__ import annotations

import json
from pathlib import Path
import uuid

import click
import pytest
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.core.context import Memory, MemoryRef, QueryContextRef
from memcommit.application.capabilities.reviewing.memory_issue.finding.detection import (
    FindingsError,
    collect_direct_memories,
    enumerate_pairs,
    find_ambiguities,
    find_conflicts,
    find_redundancies as find_duplicates,
)
from memcommit.adapters.console.terminal.core.identity import (
    collision_safe_uid_prefixes,
)
from memcommit.adapters.console.terminal.core.theme import (
    SemanticColorRole,
    semantic_color_rgb,
)
from memcommit.application.operations.profile.model import ProfileError
from memcommit.persistence.store import MemoryStore


runner = CliRunner()
PAYLOAD_MARKER = "QUALITY FIND PAYLOAD:\n"
FIXTURE_DIR = (
    Path(__file__).parents[1]
    / "src"
    / "memcommit"
    / "application"
    / "capabilities"
    / "evaluation"
    / "fixtures"
)


class PayloadProvider:
    """Return structured findings chosen from one complete operation payload."""

    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str, dict[str, object] | None, dict]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        payload = json.loads(prompt.split(PAYLOAD_MARKER, 1)[1])
        self.calls.append((prompt, operation, output_schema, payload))
        return json.dumps(self.responder(operation, payload))


class ForbiddenProvider:
    def __call__(self):
        raise AssertionError("provider should not be connected")


def _pair_id_for_contents(payload: dict, left: str, right: str) -> str:
    contents = {
        memory["candidate_id"]: memory["content"] for memory in payload["memories"]
    }
    for pair in payload["pairs"]:
        pair_contents = {
            contents[pair["left_id"]],
            contents[pair["right_id"]],
        }
        if pair_contents == {left, right}:
            return pair["pair_id"]
    raise AssertionError(f"pair not found: {left!r}, {right!r}")


def _candidate_id_for_content(payload: dict, content: str) -> str:
    for memory in payload["memories"]:
        if memory["content"] == content:
            return memory["candidate_id"]
    raise AssertionError(f"candidate not found: {content!r}")


def test_direct_collection_excludes_refs_children_and_query_only_items():
    source = ops.init("source")
    referenced = ops.add(source, "referenced fact")
    child = ops.init("child")
    ops.add(child, "nested fact")
    root = ops.init("root")
    first = ops.add(root, "first direct fact")
    root.add(
        MemoryRef(
            uid="memory-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    root.add(
        QueryContextRef(
            uid="query-ref",
            name="restricted-policy",
            target_source_uid="secret-source",
            provider="codex_chatgpt",
        )
    )
    root.add(child)
    second = ops.add(root, "second direct fact")

    candidates = collect_direct_memories(root)

    assert [candidate.memory for candidate in candidates] == [first, second]
    assert [candidate.candidate_id for candidate in candidates] == [
        "m000001",
        "m000002",
    ]


def test_pair_enumeration_is_complete_unordered_and_canonical():
    ctx = ops.init("pairs")
    for content in ["A", "B", "C", "D"]:
        ops.add(ctx, content)

    pairs = enumerate_pairs(collect_direct_memories(ctx))

    assert len(pairs) == 6
    assert [
        (
            pair.pair_id,
            pair.left.memory.content,
            pair.right.memory.content,
        )
        for pair in pairs
    ] == [
        ("p000001", "A", "B"),
        ("p000002", "A", "C"),
        ("p000003", "A", "D"),
        ("p000004", "B", "C"),
        ("p000005", "B", "D"),
        ("p000006", "C", "D"),
    ]


def test_find_duplicates_scans_representatives_without_pair_targets(
    monkeypatch,
):
    ctx = ops.init("duplicates")
    for content in [
        "Same content.",
        "Same content.",
        "  Surface   equivalent. ",
        "Surface equivalent.",
        "The garage is closed.",
        "The parking garage is unavailable.",
    ]:
        ops.add(ctx, content)

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(
                            payload,
                            "The parking garage is unavailable.",
                        ),
                        _candidate_id_for_content(
                            payload,
                            "The garage is closed.",
                        ),
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "Both state the same garage closure.",
                }
            ]
        }

    monkeypatch.setattr(
        "memcommit.application.capabilities.reviewing.memory_issue.finding.detection.enumerate_pairs",
        lambda candidates: pytest.fail(
            "duplicate discovery must not enumerate pair targets"
        ),
    )
    provider = PayloadProvider(respond)
    report = find_duplicates(ctx, lambda: provider)

    assert report.memory_count == 6
    assert [finding.relation for finding in report.findings] == [
        "EXACT",
        "SURFACE_EQUIVALENT",
        "SEMANTIC_EQUIVALENT",
    ]
    assert report.redundancy_count == 3
    assert report.exact_duplicate_count == 1
    assert report.semantic_redundancy_count == 2
    assert report.group_count == 3
    assert (
        report.findings[-1].left.content,
        report.findings[-1].right.content,
    ) == (
        "The garage is closed.",
        "The parking garage is unavailable.",
    )
    assert len(provider.calls) == 1
    _, operation, schema, payload = provider.calls[0]
    assert operation == "find_duplicates"
    assert payload["context"]["direct_memory_count"] == 6
    assert len(payload["memories"]) == 4
    assert "pairs" not in payload
    assert "unresolved_pairs" not in payload
    item_schema = schema["properties"]["findings"]["items"]
    assert "candidate_ids" in item_schema["properties"]
    assert "pair_id" not in item_schema["properties"]
    assert "uniqueItems" not in item_schema["properties"]["candidate_ids"]
    assert schema["properties"]["findings"]["maxItems"] == 2


def test_complete_dun_connects_exact_dup_and_semantic_dun_in_one_group():
    ctx = ops.init("inclusive-dun")
    first = ops.add(ctx, "The garage is closed.")
    exact_copy = ops.add(ctx, "The garage is closed.")
    semantic_copy = ops.add(ctx, "The parking garage is unavailable.")

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(payload, first.content),
                        _candidate_id_for_content(payload, semantic_copy.content),
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "Both state the same garage closure.",
                }
            ]
        }

    report = find_duplicates(ctx, lambda: PayloadProvider(respond))

    assert [finding.relation for finding in report.findings] == [
        "EXACT",
        "SEMANTIC_EQUIVALENT",
    ]
    assert report.exact_duplicate_count == 1
    assert report.semantic_redundancy_count == 1
    assert report.redundancy_count == 2
    assert report.group_count == 1
    assert {
        memory.uid
        for finding in report.findings
        for memory in (finding.left, finding.right)
    } == {
        first.uid,
        exact_copy.uid,
        semantic_copy.uid,
    }


def test_find_duplicates_keeps_each_stored_memory_indivisible():
    ctx = ops.init("partial-overlap")
    ops.add(ctx, "abc")
    ops.add(ctx, "bcd")
    provider = PayloadProvider(lambda operation, payload: {"findings": []})

    report = find_duplicates(ctx, lambda: provider)

    assert report.findings == ()
    assert len(provider.calls) == 1
    prompt, _operation, schema, payload = provider.calls[0]
    assert [memory["content"] for memory in payload["memories"]] == [
        "abc",
        "bcd",
    ]
    assert "complete stored content as one indivisible judgment unit" in prompt
    assert "Atomize must first" in prompt
    assert schema["properties"]["findings"]["items"]["properties"]["relation"][
        "enum"
    ] == ["SEMANTIC_EQUIVALENT"]


def test_find_duplicates_avoids_provider_for_one_mechanical_component():
    ctx = ops.init("duplicates")
    ops.add(ctx, "same")
    ops.add(ctx, "same")

    report = find_duplicates(ctx, ForbiddenProvider())

    assert [finding.relation for finding in report.findings] == ["EXACT"]
    assert report.exact_group_count == 1
    assert report.exact_duplicate_count == 1


def test_mechanical_duplicate_forest_is_linear_and_preserves_relation_tiers():
    ctx = ops.init("mechanical-forest")
    for content in ["same", "same", " same ", " same "]:
        ops.add(ctx, content)

    report = find_duplicates(ctx, ForbiddenProvider())

    assert len(report.findings) == 3
    assert [
        (
            finding.left.content,
            finding.right.content,
            finding.relation,
        )
        for finding in report.findings
    ] == [
        ("same", "same", "EXACT"),
        ("same", " same ", "SURFACE_EQUIVALENT"),
        (" same ", " same ", "EXACT"),
    ]


def test_surface_equivalence_collapses_only_horizontal_whitespace():
    horizontal = ops.init("horizontal")
    ops.add(horizontal, "  Access\tcard\u00a0required. ")
    ops.add(horizontal, "Access card required.")
    horizontal_report = find_duplicates(horizontal, ForbiddenProvider())

    assert [finding.relation for finding in horizontal_report.findings] == [
        "SURFACE_EQUIVALENT"
    ]

    for separator in ["\v", "\f", "\x85", "\u2028", "\u2029"]:
        vertical = ops.init(f"vertical-{ord(separator)}")
        ops.add(vertical, f"Access{separator}card required.")
        ops.add(vertical, "Access card required.")
        provider = PayloadProvider(lambda operation, payload: {"findings": []})

        report = find_duplicates(vertical, lambda: provider)

        assert report.findings == ()
        assert len(provider.calls) == 1


def test_find_ambiguities_calls_provider_once_and_restores_context_order():
    ctx = ops.init("ambiguities")
    first = ops.add(ctx, "Ask the coordinator.")
    ops.add(ctx, "The main entrance closes at 5 p.m.")
    third = ops.add(ctx, "It's 216.")

    def respond(operation, payload):
        assert operation == "find_ambiguities"
        ids = {
            memory["content"]: memory["candidate_id"] for memory in payload["memories"]
        }
        return {
            "findings": [
                {
                    "candidate_id": ids["It's 216."],
                    "interpretation": "COMPETING",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "Room number 216.",
                        "Price 216.",
                    ],
                    "reason": "The referent changes the booking action.",
                    "question": "Does 216 mean the room or the price?",
                },
                {
                    "candidate_id": ids["Ask the coordinator."],
                    "interpretation": "SINGLE",
                    "clarification": "REQUIRED",
                    "ordinary_readings": [
                        "Contact the responsible coordinator.",
                    ],
                    "reason": "No contact route is provided.",
                    "question": "How can the coordinator be contacted?",
                },
            ]
        }

    provider = PayloadProvider(respond)
    report = find_ambiguities(ctx, lambda: provider)

    assert report.memory_count == 3
    assert [finding.memory for finding in report.findings] == [first, third]
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == "find_ambiguities"
    assert len(provider.calls[0][3]["memories"]) == 3
    prompt = provider.calls[0][0]
    assert "Write every ordinary reading, reason, and question in English" in prompt
    assert "clean SINGLE/NONE and must be omitted" in prompt
    assert "after that time a card is required" in prompt
    assert "Never expose candidate IDs" in prompt
    assert "what cannot be determined reliably" in prompt
    assert "what remains possible" in prompt


def test_find_conflicts_sends_every_pair_once_and_sorts_findings():
    ctx = ops.init("conflicts")
    first = ops.add(ctx, "The main entrance closes after 5 p.m.")
    second = ops.add(ctx, "Staff may use the main entrance after 5 p.m.")
    third = ops.add(ctx, "The separate staff entrance stays open.")

    def respond(operation, payload):
        assert operation == "find_conflicts"
        yes_pair = _pair_id_for_contents(
            payload,
            first.content,
            second.content,
        )
        may_pair = _pair_id_for_contents(
            payload,
            second.content,
            third.content,
        )
        return {
            "findings": [
                {
                    "pair_id": may_pair,
                    "conflict": "MAY",
                    "reason": "The named entrance may or may not be the same.",
                    "question": "Do both Memories concern the staff entrance?",
                },
                {
                    "pair_id": yes_pair,
                    "conflict": "YES",
                    "reason": "The same entrance is both closed and permitted.",
                    "question": "Which main-entrance rule is authoritative?",
                },
            ]
        }

    provider = PayloadProvider(respond)
    report = find_conflicts(ctx, lambda: provider)

    assert report.memory_count == 3
    assert report.pair_count == 3
    assert [(finding.left, finding.right) for finding in report.findings] == [
        (first, second),
        (second, third),
    ]
    assert [finding.conflict for finding in report.findings] == ["YES", "MAY"]
    assert len(provider.calls) == 1
    schema = provider.calls[0][2]
    item_properties = schema["properties"]["findings"]["items"]["properties"]
    assert "scope_dimensions" not in item_properties
    assert set(item_properties) == {"pair_id", "conflict", "reason", "question"}
    payload = provider.calls[0][3]
    assert [pair["pair_id"] for pair in payload["pairs"]] == [
        "p000001",
        "p000002",
        "p000003",
    ]


def test_aggregate_finder_payload_keeps_original_context_for_each_memory():
    aggregate = ops.init("quality-find-frame")
    left = ops.add(aggregate, "The entrance opens at 8:00.")
    right = ops.add(aggregate, "The entrance stays closed until 9:00.")
    provider = PayloadProvider(lambda operation, payload: {"findings": []})

    report = find_conflicts(
        aggregate,
        lambda: provider,
        context_name_by_uid={
            left.uid: "schedule/public",
            right.uid: "schedule/staff",
        },
    )

    assert report.pair_count == 1
    assert [
        (memory["content"], memory["context_name"])
        for memory in provider.calls[0][3]["memories"]
    ] == [
        (left.content, "schedule/public"),
        (right.content, "schedule/staff"),
    ]
    assert "including cross-Context pairs" in provider.calls[0][0]


def test_empty_and_singleton_inputs_do_not_connect_provider():
    empty = ops.init("empty")
    singleton = ops.init("singleton")
    ops.add(singleton, "only one")

    assert find_ambiguities(empty, ForbiddenProvider()).findings == ()
    assert find_duplicates(empty, ForbiddenProvider()).findings == ()
    assert find_conflicts(empty, ForbiddenProvider()).findings == ()
    assert find_duplicates(singleton, ForbiddenProvider()).findings == ()
    assert find_conflicts(singleton, ForbiddenProvider()).findings == ()


@pytest.mark.parametrize(
    ("finder_name", "raw"),
    [
        ("ambiguities", None),
        ("ambiguities", "not json"),
        ("ambiguities", '{"findings": [], "findings": []}'),
        ("ambiguities", json.dumps({"wrong": []})),
        (
            "ambiguities",
            json.dumps(
                {
                    "findings": [
                        {
                            "candidate_id": "unknown",
                            "interpretation": "COMPETING",
                            "clarification": "REQUIRED",
                            "ordinary_readings": ["one", "two"],
                            "reason": "reason",
                            "question": "question?",
                        }
                    ]
                }
            ),
        ),
        (
            "conflicts",
            json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": "unknown",
                            "conflict": "YES",
                            "reason": "reason",
                            "question": "Which rule applies?",
                        }
                    ]
                }
            ),
        ),
        (
            "duplicates",
            json.dumps(
                {
                    "findings": [
                        {
                            "candidate_ids": ["m000001", "m000002"],
                            "relation": "OVERLAP",
                            "reason": "not a duplicate",
                        }
                    ]
                }
            ),
        ),
    ],
)
def test_finders_reject_invalid_or_unknown_structured_output(finder_name, raw):
    ctx = ops.init("invalid")
    ops.add(ctx, "first")
    ops.add(ctx, "second")

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return raw

    finder = {
        "ambiguities": find_ambiguities,
        "conflicts": find_conflicts,
        "duplicates": find_duplicates,
    }[finder_name]
    with pytest.raises(FindingsError):
        finder(ctx, lambda: Provider())


def test_find_conflicts_rejects_duplicate_pair_findings():
    ctx = ops.init("duplicate-output")
    ops.add(ctx, "first")
    ops.add(ctx, "second")

    def respond(operation, payload):
        finding = {
            "pair_id": payload["pairs"][0]["pair_id"],
            "conflict": "YES",
            "reason": "reason",
            "question": "Which rule applies?",
        }
        return {"findings": [finding, finding]}

    with pytest.raises(FindingsError, match="duplicate"):
        find_conflicts(ctx, lambda: PayloadProvider(respond))


def test_find_conflicts_requires_question_for_every_positive_pair():
    ctx = ops.init("missing-conflict-question")
    ops.add(ctx, "The main entrance opens at 08:00.")
    ops.add(ctx, "The main entrance remains closed until 09:00.")

    def respond(operation, payload):
        return {
            "findings": [
                {
                    "pair_id": payload["pairs"][0]["pair_id"],
                    "conflict": "YES",
                    "reason": "The same entrance cannot be open and closed.",
                    "question": "",
                }
            ]
        }

    with pytest.raises(FindingsError, match="invalid question"):
        find_conflicts(ctx, lambda: PayloadProvider(respond))


@pytest.mark.parametrize(
    "groups",
    [
        [["m000001", "unknown"]],
        [["m000001", "m000001"]],
        [
            ["m000001", "m000002"],
            ["m000002", "m000003"],
        ],
    ],
)
def test_find_duplicates_rejects_invalid_or_overlapping_groups(groups):
    ctx = ops.init("invalid-duplicate-groups")
    for content in ["first", "second", "third"]:
        ops.add(ctx, content)

    def respond(operation, payload):
        return {
            "findings": [
                {
                    "candidate_ids": candidate_ids,
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "same claim",
                }
                for candidate_ids in groups
            ]
        }

    with pytest.raises(FindingsError, match="duplicate group"):
        find_duplicates(ctx, lambda: PayloadProvider(respond))


def test_find_duplicates_canonicalizes_semantic_group_and_emits_linear_evidence():
    ctx = ops.init("semantic-group")
    memories = [
        ops.add(ctx, content)
        for content in ["first wording", "second wording", "third wording"]
    ]

    def respond(operation, payload):
        ids = [
            _candidate_id_for_content(payload, memory.content) for memory in memories
        ]
        return {
            "findings": [
                {
                    "candidate_ids": list(reversed(ids)),
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "All three are mutually substitutable.",
                }
            ]
        }

    report = find_duplicates(ctx, lambda: PayloadProvider(respond))

    assert [(finding.left, finding.right) for finding in report.findings] == [
        (memories[0], memories[1]),
        (memories[0], memories[2]),
    ]


def test_cli_redundancy_report_groups_members_once_without_left_right_labels(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("quality/grouped-report")
    contents = (
        "The garage closes at ten.",
        "Garage access ends at 22:00.",
        "The parking structure is unavailable after 10 p.m.",
    )
    for content in contents:
        ops.add(context, content)
    store.save(context)
    store.set_current(context.name)

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(payload, content)
                        for content in contents
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "All three express the same garage closing time.",
                }
            ]
        }

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_redundancies.command.connect_codex_chatgpt_provider",
        lambda: PayloadProvider(respond),
    )

    result = runner.invoke(app, ["find-redundancies"], color=True)

    assert result.exit_code == 0, result.output
    plain = click.unstyle(result.output)
    assert "DUN GROUP  1/1 · 3 Memories · SEMANTIC DUN" in plain
    assert "CLEANUP MAP · READY FOR REVIEW" in plain
    assert plain.count("SURVIVOR") == 1
    assert plain.count("ABSORB") == 2
    assert "EVIDENCE 1 · SEMANTIC EQUIVALENT" in plain
    assert "EVIDENCE 2 · SEMANTIC EQUIVALENT" in plain
    assert all(plain.count(content) == 1 for content in contents)
    assert "FIRST" not in plain
    assert "LATER" not in plain
    assert "LEFT" not in plain
    assert "RIGHT" not in plain
    assert (
        click.style(
            "SURVIVOR",
            fg=semantic_color_rgb(SemanticColorRole.ADD),
            bold=True,
        )
        in result.output
    )
    assert (
        click.style(
            "ABSORB",
            fg=semantic_color_rgb(SemanticColorRole.REMOVE),
            bold=True,
        )
        in result.output
    )


def test_cli_ambiguity_and_conflict_reports_use_truthful_compact_units(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("quality/compact-report")
    first = ops.add(context, "Call the coordinator before entering.")
    second = ops.add(context, "The main entrance opens at 08:00.")
    third = ops.add(context, "The main entrance remains closed until 09:00.")
    store.save(context)
    store.set_current(context.name)

    def respond(operation, payload):
        if operation == "find_ambiguities":
            return {
                "findings": [
                    {
                        "candidate_id": _candidate_id_for_content(
                            payload,
                            first.content,
                        ),
                        "interpretation": "SINGLE",
                        "clarification": "REQUIRED",
                        "ordinary_readings": [
                            "Call the event coordinator before entering."
                        ],
                        "reason": "No contact route is provided.",
                        "question": "How can the coordinator be contacted?",
                    }
                ]
            }
        assert operation == "find_conflicts"
        return {
            "findings": [
                {
                    "pair_id": _pair_id_for_contents(
                        payload,
                        second.content,
                        third.content,
                    ),
                    "conflict": "YES",
                    "reason": "The same entrance cannot have both opening times.",
                    "question": "Which opening time is authoritative?",
                },
                {
                    "pair_id": _pair_id_for_contents(
                        payload,
                        first.content,
                        second.content,
                    ),
                    "conflict": "MAY",
                    "reason": (
                        "The coordinator instruction may govern a different "
                        "entrance procedure."
                    ),
                    "question": "Does the coordinator instruction govern this entrance?",
                },
            ]
        }

    provider = PayloadProvider(respond)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_ambiguities.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_conflicts.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    ambiguity = click.unstyle(runner.invoke(app, ["find-ambiguities"]).output)
    conflict = click.unstyle(runner.invoke(app, ["find-conflicts"]).output)

    assert (
        "Find Ambiguities · quality/compact-report · 1/3 direct memories flagged"
    ) in ambiguity
    assert "UNDERSPECIFIED 1/1" in ambiguity
    assert f"[{first.uid[:8]}] {first.content}" in ambiguity
    assert "Reading: Call the event coordinator before entering." in ambiguity
    assert "Reason: No contact route is provided." in ambiguity
    assert "Question: How can the coordinator be contacted?" in ambiguity
    assert "SINGLE" not in ambiguity
    assert "REQUIRED" not in ambiguity
    assert "finding" not in ambiguity.casefold()

    assert (
        "Find Conflicts · quality/compact-report · "
        "3/3 direct memories involved · 2/3 pairs flagged"
    ) in conflict
    assert "POSSIBLE CONFLICT 1/2" in conflict
    assert "CONFLICT 2/2" in conflict
    assert f"[{second.uid[:8]}] {second.content}" in conflict
    assert "Question: Which opening time is authoritative?" in conflict
    assert "LEFT" not in conflict
    assert "RIGHT" not in conflict
    assert "Scope" not in conflict
    assert "finding" not in conflict.casefold()


def test_cli_exact_duplicate_report_keeps_each_disposition_row_self_contained(
    isolated_store,
):
    store = MemoryStore()
    context = ops.init("quality/exact-cleanup-map")
    survivor = Memory(
        "aaaaaaaa-1111-4111-8111-111111111111",
        "Badge access is required.",
    )
    absorbed = Memory(
        "aaaaaaaa-2222-4222-8222-222222222222",
        survivor.content,
    )
    context.add(survivor)
    context.add(absorbed)
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(app, ["find-duplicates"], color=True)

    assert result.exit_code == 0, result.output
    plain = click.unstyle(result.output)
    prefixes = collision_safe_uid_prefixes((survivor.uid, absorbed.uid))
    assert "SHARED CONTENT" not in plain
    assert "CLEANUP MAP" not in plain
    assert plain.count(survivor.content) == 2
    assert f"SURVIVOR  [memory {prefixes[survivor.uid]}]  {survivor.content}" in plain
    assert f"ABSORB    [memory {prefixes[absorbed.uid]}]  {absorbed.content}" in plain
    assert "FIRST" not in plain
    assert "LATER" not in plain
    assert (
        click.style(
            "SURVIVOR",
            fg=semantic_color_rgb(SemanticColorRole.ADD),
            bold=True,
        )
        in result.output
    )
    assert (
        click.style(
            "ABSORB",
            fg=semantic_color_rgb(SemanticColorRole.REMOVE),
            bold=True,
        )
        in result.output
    )


def test_cli_find_duplicates_recursive_keeps_groups_under_context_headings(
    isolated_store,
):
    store = MemoryStore()
    root = ops.init("quality/exact-tree")
    root_first = ops.add(root, "root duplicate")
    root_later = ops.add(root, "root duplicate")
    child = ops.init("quality/exact-tree/child")
    child_first = ops.add(child, "child duplicate")
    child_later = ops.add(child, "child duplicate")
    store.save(root)
    store.save(child)
    store.set_current(root.name)

    result = runner.invoke(app, ["find-duplicates", root.name, "-r"])

    assert result.exit_code == 0, result.output
    assert "2 Contexts checked" in result.output
    assert "2 exact groups" in result.output
    assert "CONTEXT 1/2 · quality/exact-tree" in result.output
    assert "CONTEXT 2/2 · quality/exact-tree/child" in result.output
    assert root_first.uid in store.load_direct(root.name).memories
    assert root_later.uid in store.load_direct(root.name).memories
    assert child_first.uid in store.load_direct(child.name).memories
    assert child_later.uid in store.load_direct(child.name).memories
    assert store.list_checkpoints(root.name) == []
    assert store.list_checkpoints(child.name) == []


def test_cli_finders_are_read_only_and_each_use_one_provider_call(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("quality")
    ops.add(ctx, "The entrance closes at 5 p.m.")
    ops.add(ctx, "Staff may enter after 5 p.m.")
    store.save(ctx)
    store.set_current(ctx.name)
    context_path = store._context_file(ctx.name)
    context_before = context_path.read_bytes()
    checkpoints_before = store.list_checkpoints(ctx.name)

    provider = PayloadProvider(lambda operation, payload: {"findings": []})
    for module_name in [
        "find_redundancies",
        "find_ambiguities",
        "find_conflicts",
    ]:
        monkeypatch.setattr(
            f"memcommit.adapters.console.commands.{module_name}.command.connect_codex_chatgpt_provider",
            lambda: provider,
        )

    redundancy_result = runner.invoke(app, ["find-redundancies"])
    dedun_result = runner.invoke(app, ["dedun"])
    ambiguity_result = runner.invoke(app, ["find-ambiguities"])
    conflict_result = runner.invoke(app, ["find-conflicts"])

    assert redundancy_result.exit_code == 0
    assert dedun_result.exit_code == 0
    assert ambiguity_result.exit_code == 0
    assert conflict_result.exit_code == 0
    assert "pair" not in redundancy_result.output
    assert (
        "Find Redundancies · quality · 2 direct memories checked"
        in redundancy_result.output
    )
    assert "0 groups · 0 proposed absorptions" in redundancy_result.output
    assert "findings" not in redundancy_result.output
    assert "No redundancies in 'quality'." in dedun_result.output
    assert (
        "Find Ambiguities · quality · 0/2 direct memories flagged"
        in ambiguity_result.output
    )
    assert (
        "Find Conflicts · quality · 0/2 direct memories involved · "
        "0/1 pairs flagged" in conflict_result.output
    )
    assert [call[1] for call in provider.calls] == [
        "find_duplicates",
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert context_path.read_bytes() == context_before
    assert store.list_checkpoints(ctx.name) == checkpoints_before
    assert store.current_context_name() == ctx.name


def test_quality_finder_all_aliases_freeze_one_profile_wide_source(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    first = ops.init("quality/first")
    second = ops.init("quality/second")
    ops.add(first, "The entrance closes at five.")
    ops.add(second, "Staff may enter after five.")
    for context in (first, second):
        store.save(context)
    store.set_current(first.name)

    def respond(operation, payload):
        if operation == "find_ambiguities":
            return {
                "findings": [
                    {
                        "candidate_id": payload["memories"][0]["candidate_id"],
                        "interpretation": "SINGLE",
                        "clarification": "REQUIRED",
                        "ordinary_readings": ["The public entrance closes at five."],
                        "reason": "The affected entrance needs clarification.",
                        "question": "Which entrance closes?",
                    }
                ]
            }
        return {
            "findings": [
                {
                    "pair_id": payload["pairs"][0]["pair_id"],
                    "conflict": "MAY",
                    "reason": "The access rule may distinguish staff.",
                    "question": "Does the closure apply to staff?",
                }
            ]
        }

    provider = PayloadProvider(respond)
    for module_name in ("find_ambiguities", "find_conflicts"):
        monkeypatch.setattr(
            f"memcommit.adapters.console.commands.{module_name}.command.connect_codex_chatgpt_provider",
            lambda: provider,
        )
    authorized = []
    monkeypatch.setattr(
        "memcommit.application.capabilities.reviewing.memory_issue.finding.source.authorize_combination",
        lambda accesses: authorized.append(
            tuple(access.display_name for access in accesses)
        ),
    )

    ambiguity = runner.invoke(app, ["find-ambiguities", "--all"])
    conflict = runner.invoke(app, ["find-conflicts", "-a"])

    assert ambiguity.exit_code == 0, ambiguity.output
    assert conflict.exit_code == 0, conflict.output
    assert "Find Ambiguities · ALL READABLE CONTEXTS" in ambiguity.output
    assert "Find Conflicts · ALL READABLE CONTEXTS" in conflict.output
    assert f"CONTEXT {first.name}" in ambiguity.output
    assert f"CONTEXT {first.name}" in conflict.output
    assert f"CONTEXT {second.name}" in conflict.output
    expected_contents = [
        "The entrance closes at five.",
        "Staff may enter after five.",
    ]
    assert [call[1] for call in provider.calls] == [
        "find_ambiguities",
        "find_conflicts",
    ]
    assert [
        [memory["content"] for memory in call[3]["memories"]] for call in provider.calls
    ] == [expected_contents, expected_contents]
    expected_names = (first.name, second.name)
    assert authorized == [expected_names, expected_names]
    assert store.current_context_name() == first.name


@pytest.mark.parametrize("command_name", ["find-ambiguities", "find-conflicts"])
def test_quality_finder_all_rejects_explicit_context(
    isolated_store,
    command_name,
):
    store = MemoryStore()
    context = ops.init("quality/source")
    store.save(context)
    store.set_current(context.name)

    result = runner.invoke(
        app,
        [command_name, "--all", "--context", context.name],
    )

    assert result.exit_code == 1
    assert "--all/-a cannot be combined with an explicit Context" in result.output


def test_quality_finder_all_authority_failure_precedes_provider_connection(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context = ops.init("quality/source")
    ops.add(context, "A provider-visible Memory.")
    store.save(context)
    store.set_current(context.name)
    monkeypatch.setattr(
        "memcommit.application.capabilities.reviewing.memory_issue.finding.source.authorize_combination",
        lambda _accesses: (_ for _ in ()).throw(ProfileError("combine denied")),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_ambiguities.command.connect_codex_chatgpt_provider",
        ForbiddenProvider(),
    )

    result = runner.invoke(app, ["find-ambiguities", "--all"])

    assert result.exit_code == 1
    assert "combine denied" in result.output


@pytest.mark.parametrize(
    "command_name",
    [
        "dedun",
        "find-redundancies",
        "find-duplicates",
        "find-ambiguities",
        "find-conflicts",
    ],
)
def test_cli_positional_context_does_not_switch_current(
    isolated_store,
    monkeypatch,
    command_name,
):
    store = MemoryStore()
    active = ops.init("active")
    target = ops.init("target")
    ops.add(target, "same")
    ops.add(target, "same")
    store.save(active)
    store.save(target)
    store.set_current(active.name)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_redundancies.command.connect_codex_chatgpt_provider",
        lambda: PayloadProvider(lambda _operation, _payload: {"findings": []}),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_ambiguities.command.connect_codex_chatgpt_provider",
        lambda: PayloadProvider(lambda _operation, _payload: {"findings": []}),
    )
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_conflicts.command.connect_codex_chatgpt_provider",
        lambda: PayloadProvider(lambda _operation, _payload: {"findings": []}),
    )

    result = runner.invoke(
        app,
        [command_name, target.name],
    )

    assert result.exit_code == 0
    if command_name == "dedun":
        assert "Dedun 'target': absorbed 1 redundant direct item(s)" in result.output
        assert "1 DUP / EXACT link" in result.output
    elif command_name == "find-redundancies":
        assert "Find Redundancies · target · 2 direct memories checked" in result.output
        assert "1 group · 1 proposed absorption" in result.output
        assert "redundancy finding" not in result.output
        assert "DUN GROUP  1/1 · 2 Memories · DUP / EXACT" in result.output
        assert "CLEANUP MAP · READY FOR REVIEW" in result.output
        assert "SURVIVOR" in result.output
        assert "ABSORB" in result.output
        assert "FIRST" not in result.output
        assert "LATER" not in result.output
        assert "LEFT" not in result.output
        assert "RIGHT" not in result.output
    elif command_name == "find-duplicates":
        assert (
            "Find Duplicates · target · 2 direct items checked · "
            "1 exact group · 1 proposed absorption"
        ) in result.output
        assert result.output.count("same") == 2
        assert "SURVIVOR" in result.output
        assert "ABSORB" in result.output
        assert "SHARED CONTENT" not in result.output
        assert "CLEANUP MAP" not in result.output
        assert "FIRST" not in result.output
        assert "LATER" not in result.output
        assert "Apply exact cleanup with mem dedup" in result.output
    elif command_name == "find-ambiguities":
        assert (
            "Find Ambiguities · target · 0/2 direct memories flagged" in result.output
        )
    else:
        assert (
            "Find Conflicts · target · 0/2 direct memories involved · 0/1 pairs flagged"
        ) in result.output
    assert store.current_context_name() == active.name


def test_cli_direct_scope_does_not_open_memory_ref_or_embedded_context_files(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("source")
    referenced = ops.add(source, "referenced content")
    child = ops.init("child")
    ops.add(child, "nested content")
    root = ops.init("root")
    ops.add(root, "first direct")
    root.add(
        MemoryRef(
            uid="memory-ref",
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=referenced.uid,
            target=referenced,
        )
    )
    root.add(child)
    ops.add(root, "second direct")
    for context in [source, child, root]:
        store.save(context)
    store.set_current(root.name)

    # A direct-only scan must remain usable even when out-of-scope targets are
    # unreadable. Query-only sources are never opened by either load path.
    store._context_file(source.name).write_text("{invalid")
    store._context_file(child.name).write_text("{invalid")
    provider = PayloadProvider(lambda operation, payload: {"findings": []})
    for module_name in [
        "find_redundancies",
        "find_ambiguities",
        "find_conflicts",
    ]:
        monkeypatch.setattr(
            f"memcommit.adapters.console.commands.{module_name}.command.connect_codex_chatgpt_provider",
            lambda: provider,
        )

    results = [
        runner.invoke(app, [command])
        for command in [
            "dedun",
            "find-ambiguities",
            "find-conflicts",
        ]
    ]

    assert [result.exit_code for result in results] == [0, 0, 0]
    assert "No redundancies in 'root'." in results[0].output
    assert all("2 direct memories" in result.output for result in results[1:])
    assert [call[1] for call in provider.calls] == [
        "find_duplicates",
        "find_ambiguities",
        "find_conflicts",
    ]
    assert all(
        [item["content"] for item in call[3]["memories"]]
        == ["first direct", "second direct"]
        for call in provider.calls
    )


def test_cli_dedun_immediately_applies_eligible_groups_and_prints_review_receipt(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    ctx = ops.init("dedun/direct")
    first = ops.add(ctx, "The parking garage is unavailable.")
    second = ops.add(ctx, "The garage is closed.")
    unrelated = ops.add(ctx, "The lobby opens at eight.")
    store.save(ctx)
    store.set_current(ctx.name)

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(payload, first.content),
                        _candidate_id_for_content(payload, second.content),
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "Both Memories state the same garage closure.",
                }
            ]
        }

    provider = PayloadProvider(respond)
    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_redundancies.command.connect_codex_chatgpt_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["dedun"])

    assert result.exit_code == 0, result.output
    assert "absorbed 1 redundant direct item(s)" in result.output
    assert "mem review dedun --receipt" in result.output
    current = store.load_direct(ctx.name)
    assert tuple(current.memories) == (first.uid, unrelated.uid)
    checkpoint = store.list_checkpoints(ctx.name)[0]
    assert checkpoint["command"] == "dedun"
    assert checkpoint["args"]["components"][0]["survivor_uid"] == first.uid


def test_cli_dedun_unions_semantic_memory_and_exact_embed_groups_atomically(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    source = ops.init("dedun/mixed-source")
    source_memory = ops.add(source, "Source-owned live content.")
    target = ops.init("dedun/mixed-target")
    first = ops.add(target, "The garage is unavailable.")
    second = ops.add(target, "The garage is closed.")
    live_refs = tuple(
        MemoryRef(
            uid=str(uuid.uuid4()),
            target_context_uid=source.uid,
            target_context_name=source.name,
            target_memory_uid=source_memory.uid,
            target=source_memory,
        )
        for _ in range(2)
    )
    for reference in live_refs:
        target.add(reference)
    store.save(source)
    store.save(target)
    store.set_current(target.name)

    def respond(operation, payload):
        assert operation == "find_duplicates"
        return {
            "findings": [
                {
                    "candidate_ids": [
                        _candidate_id_for_content(payload, first.content),
                        _candidate_id_for_content(payload, second.content),
                    ],
                    "relation": "SEMANTIC_EQUIVALENT",
                    "reason": "Both Memories state the same garage closure.",
                }
            ]
        }

    monkeypatch.setattr(
        "memcommit.adapters.console.commands.find_redundancies.command.connect_codex_chatgpt_provider",
        lambda: PayloadProvider(respond),
    )

    result = runner.invoke(app, ["dedun"])

    assert result.exit_code == 0, result.output
    assert "absorbed 2 redundant direct item(s)" in result.output
    assert (
        "2 evidence links = 1 DUP / EXACT link + 1 SEMANTIC DUN link" in result.output
    )
    current = store.load_direct(target.name)
    assert first.uid in current.memories
    assert second.uid not in current.memories
    assert live_refs[0].uid in current.memories
    assert live_refs[1].uid not in current.memories
    checkpoints = store.list_checkpoints(target.name)
    assert len(checkpoints) == 1
    assert len(checkpoints[0]["args"]["components"]) == 1
    assert len(checkpoints[0]["args"]["exact_item_groups"]) == 1


def test_conflicts_enumerates_all_pairs_without_count_gate():
    ctx = ops.init("large")
    for index in range(4):
        ops.add(ctx, str(index))
    provider = PayloadProvider(lambda _operation, _payload: {"findings": []})

    report = find_conflicts(ctx, lambda: provider)

    assert report.findings == ()
    assert len(provider.calls[0][3]["pairs"]) == 6


def test_duplicate_scan_does_not_allocate_pair_records(monkeypatch):
    ctx = ops.init("linear-duplicates")
    for index in range(4):
        ops.add(ctx, str(index))
    monkeypatch.setattr(
        "memcommit.application.capabilities.reviewing.memory_issue.finding.detection.MemoryPair",
        lambda *args, **kwargs: pytest.fail(
            "duplicate discovery allocated a pair record"
        ),
    )
    provider = PayloadProvider(lambda operation, payload: {"findings": []})

    report = find_duplicates(ctx, lambda: provider)

    assert report.memory_count == 4
    assert report.findings == ()
    assert len(provider.calls) == 1
    assert "pairs" not in provider.calls[0][3]


def test_enumerate_pairs_has_no_fixed_pair_count_gate():
    ctx = ops.init("large")
    for index in range(4):
        ops.add(ctx, str(index))
    candidates = collect_direct_memories(ctx)
    pairs = enumerate_pairs(candidates)

    assert len(pairs) == 6
    assert [pair.pair_id for pair in pairs] == [
        "p000001",
        "p000002",
        "p000003",
        "p000004",
        "p000005",
        "p000006",
    ]


def test_ambiguity_fixture_covers_the_complete_three_by_three_matrix():
    data = json.loads((FIXTURE_DIR / "ambiguity.json").read_text())
    combinations = {
        (
            case["expected"]["interpretation"],
            case["expected"]["clarification"],
        )
        for case in data["cases"]
    }

    assert data["schema_version"] == 1
    assert any(
        case["id"] == "single-none-context-resolved-time"
        and case["expected"]["clarification"] == "NONE"
        for case in data["cases"]
    )
    assert combinations == {
        (interpretation, clarification)
        for interpretation in ["SINGLE", "DOMINANT", "COMPETING"]
        for clarification in ["NONE", "HELPFUL", "REQUIRED"]
    }
    assert all(isinstance(case["expected"]["question"], str) for case in data["cases"])


def test_conflict_and_duplicate_fixtures_cover_all_calibration_boundaries():
    conflict = json.loads((FIXTURE_DIR / "conflict.json").read_text())
    duplicates = json.loads((FIXTURE_DIR / "duplicates.json").read_text())

    assert {case["expected"]["conflict"] for case in conflict["cases"]} == {
        "YES",
        "MAY",
        "NO",
    }
    assert all("scope_dimensions" not in case["expected"] for case in conflict["cases"])
    assert {case["expected"]["relation"] for case in duplicates["cases"]} == {
        "EXACT",
        "SURFACE_EQUIVALENT",
        "SEMANTIC_EQUIVALENT",
        "OVERLAP",
        "UNKNOWN",
        "DISTINCT",
    }
