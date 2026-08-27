import json
from types import SimpleNamespace
import uuid

import memcommit.ops as ops
import memcommit.eval.study_compare_graph_prewarm as graph_prewarm
from memcommit.comparison import (
    ComparisonAnalysis,
    ComparisonMember,
    ComparisonRelation,
    ComparisonReports,
)
from memcommit.context import Context
from memcommit.eval.study_compare_graph_prewarm import (
    GraphPair,
    TaskGraphPlan,
    _identity_containment,
    _pair_key,
    _view,
    compute_pair,
    project_pair_deletions,
    run_graph_prewarm,
)
from memcommit.eval.study_compare_exact_matrix import declared_exact_plans
from memcommit.provider_types import ProviderIdentity


class _Provider:
    def __init__(self):
        self.calls = 0
        self.identity = ProviderIdentity(
            provider="codex_chatgpt",
            model="gpt-5.6-sol",
            runtime="test",
            reasoning_effort="medium",
        )
        self.last_run = None

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        return json.dumps(
            {
                "reference_group_ids": [1],
                "compared_group_ids": [2],
                "groups": [
                    {"kind": "DISTINCT", "note": ""},
                    {"kind": "DISTINCT", "note": ""},
                ],
                "issues": [],
            }
        )


def _context(name: str, content: str | None) -> Context:
    context = Context(uid=str(uuid.uuid4()), name=name)
    if content is not None:
        ops.add(context, content)
    return context


def _pair(left: Context, right: Context) -> GraphPair:
    left_view = _view("tutorial", left)
    right_view = _view("tutorial", right)
    description_digest = left_view.context_digest
    return GraphPair(
        task="tutorial",
        description_digest=description_digest,
        left=left_view,
        right=right_view,
        key=_pair_key(
            task="tutorial",
            description_digest=description_digest,
            left=left_view,
            right=right_view,
            model="gpt-5.6-sol",
            reasoning="medium",
        ),
    )


def test_graph_prewarm_is_hidden_compact_and_resumable(tmp_path):
    pair = _pair(
        _context("practice/description", "private description"),
        _context("practice/source", "private source"),
    )
    plan = TaskGraphPlan(
        task="tutorial",
        description_name=pair.left.name,
        description_digest=pair.description_digest,
        views=(pair.left, pair.right),
        pairs=(pair,),
    )
    providers: list[_Provider] = []

    def provider_factory():
        provider = _Provider()
        providers.append(provider)
        return provider

    first = run_graph_prewarm(
        (plan,),
        output_root=tmp_path,
        provider_factory=provider_factory,
        profile_name="study-test",
        profile_uid=str(uuid.uuid4()),
        model="gpt-5.6-sol",
        reasoning="medium",
        workers=1,
    )
    second = run_graph_prewarm(
        (plan,),
        output_root=tmp_path,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("resume must not connect a provider")
        ),
        profile_name="study-test",
        profile_uid=first["profile_uid"],
        model="gpt-5.6-sol",
        reasoning="medium",
        workers=1,
    )

    assert sum(provider.calls for provider in providers) == 1
    assert first["completed_count"] == 1
    assert second["reused_count"] == 1
    pair_path = next((tmp_path / "tutorial" / "pairs").glob("*.json"))
    serialized = pair_path.read_text(encoding="utf-8")
    assert "private description" not in serialized
    assert "private source" not in serialized
    assert json.loads(serialized)["semantic_content_in_participant_report"] is False


def test_empty_view_pair_is_deterministic_and_does_not_connect(tmp_path):
    pair = _pair(
        _context("task-2/participant", None),
        _context("task-2/advisor1", "one policy"),
    )
    plan = TaskGraphPlan(
        task="tutorial",
        description_name=pair.left.name,
        description_digest=pair.description_digest,
        views=(pair.left, pair.right),
        pairs=(pair,),
    )
    summary = run_graph_prewarm(
        (plan,),
        output_root=tmp_path,
        provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("empty-view pair must not connect a provider")
        ),
        profile_name="study-test",
        profile_uid=str(uuid.uuid4()),
        model="gpt-5.6-sol",
        reasoning="medium",
        workers=1,
    )

    assert summary["method_counts"] == {"DETERMINISTIC_EMPTY_VIEW": 1}


def test_identity_containment_is_deterministic_and_exactly_covered():
    shared = _context("task-1/child", "shared")
    parent = _context("task-1/parent", "parent only")
    parent.add(next(iter(shared.iter_items())))
    pair = _pair(parent, shared)

    assert _identity_containment(pair) is True
    artifact = compute_pair(pair, None)

    assert artifact["method"] == "DETERMINISTIC_IDENTITY_CONTAINMENT"
    assert artifact["coverage"] == {"expected": 3, "observed": 3}
    assert [relation["kind"] for relation in artifact["relations"]] == [
        "DISTINCT",
        "EQUIVALENT",
    ]


def test_invalid_compact_pair_falls_back_to_exhaustive(monkeypatch):
    pair = _pair(
        _context("task-1/source", "incoming"),
        _context("task-1/target", "baseline"),
    )
    monkeypatch.setattr(
        graph_prewarm,
        "run_compact_compare",
        lambda *_args, **_kwargs: SimpleNamespace(
            analysis=None,
            evidence={
                "provider_seconds": 2.0,
                "validation_error": "bad vector",
            },
        ),
    )

    def exhaustive(comparison_input, _provider):
        relations = []
        for ordinal, frame in enumerate(comparison_input.frames, start=1):
            relations.append(
                ComparisonRelation.from_dict(
                    {
                        "uid": str(uuid.uuid4()),
                        "kind": "DISTINCT",
                        "status": "RESOLVED",
                        "members": [
                            ComparisonMember(
                                frame_uid=frame.uid,
                                memory_uid=frame.memories[0].uid,
                            ).to_dict()
                        ],
                        "summary": f"Distinct side {ordinal}.",
                        "reason": "The claims are independent.",
                    }
                )
            )
        return ComparisonAnalysis.create(
            comparison_input,
            overview="Two independent test claims.",
            reports=ComparisonReports(
                both="",
                differences="",
                reference_only="One reference-only relation.",
                compared_only="One compared-only relation.",
            ),
            relations=relations,
            issues=(),
        )

    monkeypatch.setattr(graph_prewarm, "analyze_comparison", exhaustive)
    artifact = compute_pair(pair, _Provider())

    assert artifact["method"] == "COMPACT_FALLBACK_EXHAUSTIVE_V1"
    assert artifact["provider"]["provider_calls"] == 2
    assert artifact["provider"]["compact_validation_error"] == "bad vector"


def test_deletion_projection_removes_and_shape_repairs_members():
    artifact = {
        "kind": "STUDY_COMPARE_GRAPH_PAIR",
        "relations": [
            {
                "relation_key": "r000001",
                "kind": "COMPATIBLE",
                "status": "RESOLVED",
                "members": [
                    {"side": "LEFT", "memory_uid": "left"},
                    {"side": "RIGHT", "memory_uid": "right"},
                ],
                "comment": "",
            }
        ],
        "issues": [],
    }

    projected = project_pair_deletions(artifact, {"right"})

    assert projected["state"] == "PROJECTED_FROM_PREWARM"
    assert projected["relations"][0]["kind"] == "DISTINCT"
    assert projected["relations"][0]["members"] == [
        {"side": "LEFT", "memory_uid": "left"}
    ]
    assert projected["coverage"] == {"expected": 1, "observed": 1}


def test_exact_matrix_manifest_uses_old_region_only_to_enumerate_real_calls():
    left_parent = _context("task-1/left", "left parent")
    left_child = _context("task-1/left/child", "left child")
    right_parent = _context("task-1/right", "right parent")
    right_child = _context("task-1/right/child", "right child")
    left_parent.add(next(iter(left_child.iter_items())))
    right_parent.add(next(iter(right_child.iter_items())))
    parent_pair = _pair(left_parent, right_parent)
    parent_input = graph_prewarm.ComparisonInput.from_contexts(
        left_parent,
        right_parent,
        reference_descendants=True,
        compared_descendants=True,
    )
    relations = tuple(
        ComparisonRelation.from_dict(
            {
                "uid": str(uuid.uuid4()),
                "kind": "DISTINCT",
                "status": "RESOLVED",
                "members": [
                    ComparisonMember(
                        frame_uid=frame.uid,
                        memory_uid=memory.uid,
                    ).to_dict()
                ],
                "summary": "One exact frozen claim.",
                "reason": "The claim is independently covered.",
            }
        )
        for frame in parent_input.frames
        for memory in frame.memories
    )
    parent = ComparisonAnalysis.create(
        parent_input,
        overview="The complete parent pair was compared.",
        reports=ComparisonReports(
            both="",
            differences="",
            reference_only="Reference claims are distinct.",
            compared_only="Compared claims are distinct.",
        ),
        relations=relations,
        issues=(),
    )
    child_pair = GraphPair(
        task="task-1",
        description_digest=parent_pair.description_digest,
        left=_view("task-1", left_child),
        right=_view("task-1", right_child),
        key="child",
    )
    outside_pair = GraphPair(
        task="task-1",
        description_digest=parent_pair.description_digest,
        left=_view("task-1", _context("task-1/outside", "outside")),
        right=_view("task-1", right_child),
        key="outside",
    )
    empty_pair = GraphPair(
        task="task-1",
        description_digest=parent_pair.description_digest,
        left=_view("task-1", _context("task-1/empty", None)),
        right=_view("task-1", right_child),
        key="empty",
    )
    plan = TaskGraphPlan(
        task="task-1",
        description_name=left_parent.name,
        description_digest=parent_pair.description_digest,
        views=(child_pair.left, child_pair.right, outside_pair.left),
        pairs=(child_pair, outside_pair, empty_pair),
    )

    selected = declared_exact_plans((plan,), parents=(parent,))

    assert selected == (child_pair,)
