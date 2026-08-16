"""Public Resolve application, semantic, and durable boundary tests."""

from __future__ import annotations

import json
import re
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.commands.resolve as resolve_command
from memcommit.cli import app
from memcommit.api import (
    MemCommitClient,
    ResolveAnalysisResult,
    ResolveApplyResult,
    SemanticAuthorityError,
    SemanticContextError,
)
from memcommit.context import Memory, MemoryRef
from memcommit.interfaces.agent import (
    RESOLVE_AGENT_TOOL_NAME,
    build_default_agent_tool_registry,
)
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, update_authority_grant
from memcommit.interfaces.tui.operations.resolve import (
    project_resolve_analysis,
    resolve_candidate_exact_review,
    run_resolve_tui,
)
from memcommit.resolve_application import (
    ResolveConflictError,
    ResolveError,
    ResolveRequest,
    apply_resolve,
    run_resolve,
)
from memcommit.resolve_runtime import MemoryStoreResolvePort
from memcommit.resolve_semantic import ProviderResolveSemanticPort
from memcommit.store import MemoryStore


FIT_MARKER = "FIT PROPOSITION PAYLOAD:\n"
VERIFY_MARKER = "VERIFY PAYLOAD:\n"
runner = CliRunner(mix_stderr=False)


class ResolveFixtureProvider:
    def __init__(
        self,
        *,
        initial_verdict: str = "NO",
        effect_kind: str = "UPDATE",
    ) -> None:
        self.initial_verdict = initial_verdict
        self.effect_kind = effect_kind
        self.operations: list[str] = []

    @staticmethod
    def _fit(prompt: str, *, initial_verdict: str) -> dict[str, object]:
        payload = json.loads(prompt.split(FIT_MARKER, 1)[1])
        judgments: list[dict[str, object]] = []
        for question in payload["questions"]:
            aliases = [
                item["proposition_id"]
                for item in (*question["background"], *question["propositions"])
            ]
            initial = question["question_id"] == "resolve-initial"
            verdict = initial_verdict if initial else "YES"
            judgments.append(
                {
                    "question_id": question["question_id"],
                    "verdict": verdict,
                    "reason": (
                        "The original times conflict."
                        if initial
                        else "The revised complete frame is compatible."
                    ),
                    "considered_proposition_ids": aliases,
                    "material_proposition_ids": aliases if verdict != "YES" else [],
                    "consistent_reading": (
                        "One statement has a narrower schedule."
                        if verdict == "MAY"
                        else ""
                    ),
                    "inconsistent_reading": (
                        "Both statements describe the same schedule."
                        if verdict == "MAY"
                        else ""
                    ),
                }
            )
        return {"overview": "Complete Fit coverage.", "judgments": judgments}

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operations.append(operation)
        if operation == "fit_propositions":
            return json.dumps(
                self._fit(prompt, initial_verdict=self.initial_verdict)
            )
        if operation == "resolve_candidates":
            if self.effect_kind == "DELETE":
                effect = {
                    "kind": "DELETE",
                    "target_id": "m2",
                    "new_content": "",
                    "source_ids": ["m2"],
                    "reason": "The explicit guidance retires the old statement.",
                }
            elif self.effect_kind == "CREATE":
                effect = {
                    "kind": "CREATE",
                    "target_id": "NEW",
                    "new_content": "The office opens at 8 on weekdays and 9 on weekends.",
                    "source_ids": ["m1", "m2"],
                    "reason": "The new scope statement preserves both schedules.",
                }
            else:
                effect = {
                    "kind": "UPDATE",
                    "target_id": "m2",
                    "new_content": "The office opens at 9 on weekends.",
                    "source_ids": ["m1", "m2"],
                    "reason": "The weekend scope makes both times compatible.",
                }
            return json.dumps(
                {
                    "question": "Which schedule scope should be authoritative?",
                    "candidates": [
                        {
                            "summary": "Separate the weekday and weekend scopes.",
                            "effects": [effect],
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": True,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": "The plan uses only cited content and guidance.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        raise AssertionError(operation)


class ResolveChoiceProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation != "resolve_candidates":
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        self.operations.append(operation)
        return json.dumps(
            {
                "question": "Choose whether to revise or add explicit scope.",
                "candidates": [
                    {
                        "summary": "Revise the second schedule.",
                        "effects": [
                            {
                                "kind": "UPDATE",
                                "target_id": "m2",
                                "new_content": "The office opens at 9 on weekends.",
                                "source_ids": ["m1", "m2"],
                                "reason": "The weekend scope preserves both claims.",
                            }
                        ],
                    },
                    {
                        "summary": "Add a shared schedule qualification.",
                        "effects": [
                            {
                                "kind": "CREATE",
                                "target_id": "NEW",
                                "new_content": "The opening time depends on the day.",
                                "source_ids": ["m1", "m2"],
                                "reason": "The qualifier is supported by both times.",
                            }
                        ],
                    },
                ],
            }
        )


class ResolveIntegratedEffectsProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation != "resolve_candidates":
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        self.operations.append(operation)
        return json.dumps(
            {
                "question": "Apply the reviewed schedule integration?",
                "candidates": [
                    {
                        "summary": "Integrate the schedules through primitive effects.",
                        "effects": [
                            {
                                "kind": "UPDATE",
                                "target_id": "m1",
                                "new_content": "The office opens at 8 on weekdays.",
                                "source_ids": ["m1", "m2"],
                                "reason": "The weekday scope preserves the first time.",
                            },
                            {
                                "kind": "DELETE",
                                "target_id": "m2",
                                "new_content": "",
                                "source_ids": ["m2"],
                                "reason": "Guidance retires the unscoped statement.",
                            },
                            {
                                "kind": "CREATE",
                                "target_id": "NEW",
                                "new_content": "The office opens at 9 on weekends.",
                                "source_ids": ["m1", "m2"],
                                "reason": "The weekend claim preserves the second time.",
                            },
                        ],
                    }
                ],
            }
        )


def _context(store: MemoryStore, *, third: bool = False):
    context = ops.init("resolve/test")
    first = ops.add(context, "The office opens at 8.")
    second = ops.add(context, "The office opens at 9.")
    if third:
        ops.add(context, "The office is closed on holidays.")
    store.save(context)
    return context, first, second


def _run(
    store: MemoryStore,
    provider: ResolveFixtureProvider,
    request: ResolveRequest,
    *,
    expected_revision: str | None = None,
):
    port = MemoryStoreResolvePort(store, current_name="resolve/test")
    return run_resolve(
        request,
        frame_port=port,
        semantic_port=ProviderResolveSemanticPort(),
        provider_factory=lambda: provider,
        expected_revision=expected_revision,
    ), port


def test_resolve_generates_verifies_and_applies_one_exact_update(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolveFixtureProvider()

    analysis, port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "PROPOSAL"
    assert analysis.initial_fit is not None
    assert analysis.initial_fit.verdict == "NO"
    assert len(analysis.candidates) == 1
    assert [effect.kind for effect in analysis.candidates[0].effects] == ["UPDATE"]
    assert provider.operations == [
        "fit_propositions",
        "resolve_candidates",
        "resolve_candidate_verification",
        "fit_propositions",
    ]

    receipt = apply_resolve(
        analysis,
        analysis.candidates[0].uid,
        frame_port=port,
    )

    loaded = store.load_direct("resolve/test")
    updated_uid = receipt.updated_uids[0]
    assert isinstance(loaded.memories[updated_uid], Memory)
    assert loaded.memories[updated_uid].content == (
        "The office opens at 9 on weekends."
    )
    assert not receipt.created_uids
    assert not receipt.deleted_uids
    checkpoints = store.list_checkpoints("resolve/test")
    assert checkpoints[0]["command"] == "resolve"
    assert checkpoints[0]["args"]["candidate_uid"] == receipt.candidate_uid


def test_resolve_already_fit_stops_after_independent_initial_fit(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolveFixtureProvider(initial_verdict="YES")

    analysis, _port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "ALREADY_FIT"
    assert not analysis.candidates
    assert provider.operations == ["fit_propositions"]


def test_resolve_expected_revision_fails_before_provider_connection(isolated_store):
    store = MemoryStore()
    _context(store)
    analysis, _port = _run(
        store,
        ResolveFixtureProvider(),
        ResolveRequest("resolve/test"),
    )
    changed = store.load_for_update("resolve/test")
    ops.add(changed, "A concurrent statement.")
    store.save(changed)

    class ForbiddenProviderFactory:
        def __call__(self):
            raise AssertionError("provider must not connect for a stale revision")

    port = MemoryStoreResolvePort(store, current_name="resolve/test")
    with pytest.raises(ResolveConflictError, match="changed"):
        run_resolve(
            ResolveRequest("resolve/test"),
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            provider_factory=ForbiddenProviderFactory(),
            expected_revision=analysis.frame.revision,
        )


def test_resolve_delete_requires_guidance() -> None:
    with pytest.raises(ResolveError, match="guidance"):
        ResolveRequest("resolve/test", allow_delete=True)


def test_resolve_delete_blocks_an_inbound_memory_reference(isolated_store):
    store = MemoryStore()
    context, _first, second = _context(store, third=True)
    observer = ops.init("resolve/observer")
    observer.add(
        MemoryRef(
            uid="observer-reference",
            target_context_uid=context.uid,
            target_context_name=context.name,
            target_memory_uid=second.uid,
        )
    )
    store.save(observer)
    analysis, port = _run(
        store,
        ResolveFixtureProvider(effect_kind="DELETE"),
        ResolveRequest(
            "resolve/test",
            allow_delete=True,
            guidance="The 9 o'clock statement is obsolete and may be retired.",
        ),
    )

    with pytest.raises(ResolveConflictError, match="inbound references"):
        apply_resolve(
            analysis,
            analysis.candidates[0].uid,
            frame_port=port,
        )
    assert second.uid in store.load_direct("resolve/test").memories


def test_resolve_create_is_opt_in(isolated_store):
    store = MemoryStore()
    _context(store)
    analysis, port = _run(
        store,
        ResolveFixtureProvider(effect_kind="CREATE"),
        ResolveRequest("resolve/test", allow_create=True),
    )

    receipt = apply_resolve(
        analysis,
        analysis.candidates[0].uid,
        frame_port=port,
    )

    assert len(receipt.created_uids) == 1
    created = store.load_direct("resolve/test").memories[receipt.created_uids[0]]
    assert isinstance(created, Memory)
    assert "weekdays" in created.content


def test_resolve_keeps_incomparable_minimum_effect_shapes_as_a_choice(
    isolated_store,
):
    store = MemoryStore()
    _context(store)

    analysis, _port = _run(
        store,
        ResolveChoiceProvider(),
        ResolveRequest("resolve/test", allow_create=True),
    )

    assert analysis.status == "CHOICE"
    assert len(analysis.candidates) == 2
    assert {candidate.effects[0].kind for candidate in analysis.candidates} == {
        "UPDATE",
        "CREATE",
    }


def test_resolve_integration_is_an_atomic_combination_of_primitive_effects(
    isolated_store,
):
    store = MemoryStore()
    _context(store, third=True)
    before_checkpoints = len(store.list_checkpoints("resolve/test"))
    analysis, port = _run(
        store,
        ResolveIntegratedEffectsProvider(),
        ResolveRequest(
            "resolve/test",
            allow_create=True,
            allow_delete=True,
            guidance="Retire the unscoped 9 o'clock statement after integration.",
        ),
    )

    receipt = apply_resolve(
        analysis,
        analysis.candidates[0].uid,
        frame_port=port,
    )

    assert [effect.kind for effect in analysis.candidates[0].effects] == [
        "UPDATE",
        "DELETE",
        "CREATE",
    ]
    assert len(receipt.updated_uids) == 1
    assert len(receipt.deleted_uids) == 1
    assert len(receipt.created_uids) == 1
    assert len(store.list_checkpoints("resolve/test")) == before_checkpoints + 1


def test_resolve_tui_projects_verified_effects_and_applies_selected_candidate(
    isolated_store,
):
    store = MemoryStore()
    _context(store)
    analysis, port = _run(
        store,
        ResolveFixtureProvider(),
        ResolveRequest("resolve/test"),
    )
    rendered = "".join(
        text
        for _style, text in project_resolve_analysis(analysis).render(
            focused_uid="resolve-report"
        )
    )
    applied: list[str] = []

    with create_pipe_input() as pipe_input:
        # Viewer -> Items; open the required plan; Responses selects the first
        # verified candidate; To Do opens exact review, applies, then closes.
        pipe_input.send_text("\t\r\t\r\t\t\r\r\r")
        receipt = run_resolve_tui(
            analysis,
            apply_candidate=lambda candidate_uid: (
                applied.append(candidate_uid)
                or apply_resolve(analysis, candidate_uid, frame_port=port)
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert "RESOLVE · FIT REPAIR" in rendered
    assert "GROUNDING VERIFIED" in rendered
    assert "FIT YES" in rendered
    assert receipt is not None
    assert applied == [analysis.candidates[0].uid]
    assert receipt.updated_uids


def test_resolve_exact_review_freezes_canonical_target_revision_and_candidate(
    isolated_store,
):
    store = MemoryStore()
    _context(store)
    analysis, _port = _run(
        store,
        ResolveFixtureProvider(),
        ResolveRequest("resolve/test"),
    )

    review = resolve_candidate_exact_review(analysis, analysis.candidates[0])

    assert review.argv[:4] == ("mem", "resolve", "--context", "resolve/test")
    assert "--candidate" in review.argv
    assert analysis.candidates[0].uid in review.argv
    assert analysis.frame.revision in review.argv
    assert any("one checkpoint" in effect for effect in review.effects)


def test_resolve_tui_already_fit_is_read_only(isolated_store):
    store = MemoryStore()
    _context(store)
    analysis, _port = _run(
        store,
        ResolveFixtureProvider(initial_verdict="YES"),
        ResolveRequest("resolve/test"),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        receipt = run_resolve_tui(
            analysis,
            apply_candidate=lambda _candidate_uid: pytest.fail(
                "already-Fit Resolve must not expose Apply"
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_plain_cli_replays_exact_candidate_before_apply(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    providers = [ResolveFixtureProvider(), ResolveFixtureProvider()]
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: providers.pop(0),
    )

    preview = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test", "--plain"],
    )

    assert preview.exit_code == 0, preview.output
    candidate = re.search(r"CANDIDATE 1 · (resolve-[0-9a-f]+)", preview.stdout)
    revision = re.search(r"REVISION · ([0-9a-f]{64})", preview.stdout)
    assert candidate is not None and revision is not None

    applied = runner.invoke(
        app,
        [
            "resolve",
            "--context",
            "resolve/test",
            "--candidate",
            candidate.group(1),
            "--expected-revision",
            revision.group(1),
            "--apply",
            "--plain",
        ],
    )

    assert applied.exit_code == 0, applied.output
    assert "RESOLVE APPLIED" in applied.stdout
    assert "UPDATED · 1" in applied.stdout


def test_public_resolve_returns_typed_analysis_and_exact_apply(isolated_store):
    store = MemoryStore()
    _context(store)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=ResolveFixtureProvider,
    )

    analysis = client.resolve_context("resolve/test")
    receipt = client.apply_resolve(
        analysis,
        candidate_uid=analysis.candidates[0].uid,
    )

    assert isinstance(analysis, ResolveAnalysisResult)
    assert analysis.status == "PROPOSAL"
    assert analysis.requested_effects == ("UPDATE",)
    assert isinstance(receipt, ResolveApplyResult)
    assert receipt.updated_uids == (analysis.candidates[0].effects[0].memory_uid,)
    assert (
        store.load_direct("resolve/test").memories[receipt.updated_uids[0]].content
        == "The office opens at 9 on weekends."
    )


def test_public_resolve_uses_one_current_snapshot_for_relative_context(
    isolated_store,
):
    store = MemoryStore()
    parent = ops.init("resolve")
    ops.add(parent, "The office opens at 8.")
    ops.add(parent, "The office opens at 9.")
    child = ops.init("resolve/child")
    store.save(parent)
    store.save(child)
    store.set_current(child.name)
    client = MemCommitClient(
        root=isolated_store,
        semantic_provider_factory=ResolveFixtureProvider,
    )

    analysis = client.resolve_context("..")

    assert analysis.context_name == "resolve"


def test_resolve_agent_analyzes_then_replays_exact_candidate(isolated_store):
    store = MemoryStore()
    _context(store)
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=ResolveFixtureProvider,
        )
    )
    request = {
        "version": 1,
        "kind": "analyze",
        "context_name": "resolve/test",
    }

    preview = registry.invoke(RESOLVE_AGENT_TOOL_NAME, request)
    candidate_uid = preview["result"]["candidates"][0]["uid"]
    revision = preview["result"]["revision"]
    receipt = registry.invoke(
        RESOLVE_AGENT_TOOL_NAME,
        {
            **request,
            "kind": "apply",
            "candidate_uid": candidate_uid,
            "expected_revision": revision,
        },
    )

    assert preview["ok"] is True
    assert preview["result"]["effect"] == "NONE"
    assert receipt["ok"] is True
    assert receipt["result"]["effect"] == "CHECKPOINT"
    assert receipt["result"]["candidate_uid"] == candidate_uid


def _granted_resolve_fixture(isolated_store, tmp_path, monkeypatch, permissions):
    monkeypatch.setenv("HOME", str(tmp_path))
    local = MemoryStore()
    attachment = ops.init("workspace")
    local.save(attachment)
    local.set_current(attachment.name)
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="resolve-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    target = ops.init("schedule")
    ops.add(target, "The office opens at 8.")
    ops.add(target, "The office opens at 9.")
    authority_store.save(target)
    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=target.name,
        attachment_name=attachment.name,
        public_name="shared/schedule",
        permissions=permissions,
    )
    return authority_store, grant


def test_granted_resolve_intersects_requested_and_granted_effects(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, _grant = _granted_resolve_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
        ("READ", "DERIVE", "UPDATE"),
    )
    client = MemCommitClient(
        semantic_provider_factory=ResolveFixtureProvider,
    )

    analysis = client.resolve_context("shared/schedule", allow_create=True)
    receipt = client.apply_resolve(
        analysis,
        candidate_uid=analysis.candidates[0].uid,
    )

    assert analysis.requested_effects == ("UPDATE", "CREATE")
    assert analysis.allowed_effects == ("UPDATE",)
    assert analysis.denied_effects == ("CREATE",)
    assert len(receipt.updated_uids) == 1
    assert authority_store.load_direct("schedule").memories[
        receipt.updated_uids[0]
    ].content == "The office opens at 9 on weekends."


def test_granted_resolve_without_derive_never_connects_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _authority_store, _grant = _granted_resolve_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
        ("READ", "UPDATE"),
    )
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return ResolveFixtureProvider()

    analysis = MemCommitClient(
        semantic_provider_factory=provider,
    ).resolve_context("shared/schedule")

    assert analysis.status == "NEEDS_AUTHORITY"
    assert analysis.allowed_effects == ("UPDATE",)
    assert calls == 0


def test_explicit_root_resolve_does_not_inherit_host_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _granted_resolve_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
        ("READ", "DERIVE", "UPDATE"),
    )
    calls = 0

    def provider():
        nonlocal calls
        calls += 1
        return ResolveFixtureProvider()

    with pytest.raises(SemanticContextError):
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=provider,
        ).resolve_context("shared/schedule")

    assert calls == 0


def test_granted_resolve_revalidates_revocation_before_apply(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    authority_store, grant = _granted_resolve_fixture(
        isolated_store,
        tmp_path,
        monkeypatch,
        ("READ", "DERIVE", "UPDATE"),
    )
    client = MemCommitClient(
        semantic_provider_factory=ResolveFixtureProvider,
    )
    analysis = client.resolve_context("shared/schedule")
    before = authority_store.load_direct("schedule").to_dict()

    update_authority_grant(grant.uid, permissions=("READ", "DERIVE"))

    with pytest.raises(SemanticAuthorityError):
        client.apply_resolve(
            analysis,
            candidate_uid=analysis.candidates[0].uid,
        )
    assert authority_store.load_direct("schedule").to_dict() == before
