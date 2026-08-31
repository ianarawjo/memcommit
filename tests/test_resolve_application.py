"""Public Resolve application, semantic, and durable boundary tests."""

from __future__ import annotations

import json
import uuid

import pytest
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import memcommit.application.capabilities.ops as ops
import memcommit.adapters.console.commands.quality_resolution.repair.resolve.command as resolve_command
from memcommit.adapters.console.entrypoint import app
from memcommit.adapters.python_api import (
    MemCommitClient,
    ResolveAnalysisResult,
    ResolveApplyResult,
    SemanticAuthorityError,
    SemanticContextError,
)
from memcommit.core.context import Memory, MemoryRef
from memcommit.adapters.agent.resolve import (
    RESOLVE_AGENT_CONTRACT_VERSION,
    RESOLVE_AGENT_TOOL_NAME,
)
from memcommit.adapters.agent.registry import build_default_agent_tool_registry
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    create_authority_grant,
    update_authority_grant,
)
from memcommit.adapters.console.commands.quality_resolution.repair.resolve.workbench import (
    project_resolve_analysis,
    resolve_candidate_exact_review,
    run_resolve_tui,
)
from memcommit.application.operations.quality_resolution.repair.resolve.application import (
    ResolveConflictError,
    ResolveError,
    ResolveRequest,
    ResolveSourcePrecondition,
    apply_resolve,
    run_resolve,
)
from memcommit.application.operations.quality_resolution.repair.resolve.runtime import MemoryStoreResolvePort
from memcommit.application.operations.quality_resolution.repair.resolve.rules import (
    resolve_ruleset_prompt_payload,
)
from memcommit.application.operations.quality_resolution.repair.resolve.semantic import (
    ProviderResolveSemanticPort,
)
from memcommit.application.operations.operation_lifecycle.review.model import direct_context_digest
from memcommit.persistence.store import MemoryStore


FIT_MARKER = "FIT PROPOSITION PAYLOAD:\n"
VERIFY_MARKER = "VERIFY PAYLOAD:\n"
RESOLVE_MARKER = "RESOLVE PAYLOAD:\n"
QUALITY_FIND_MARKER = "QUALITY FIND PAYLOAD:\n"
runner = CliRunner(mix_stderr=False)


def _assert_compact_applied_receipt(
    result,
    *,
    context_name: str = "resolve/test",
    effects: str = "UPDATE 1",
    fit_verdict: str = "YES",
) -> None:
    lines = result.stdout.splitlines()
    assert lines[:2] == [
        f"RESOLVE · {context_name}",
        f"APPLIED · {effects} · FIT {fit_verdict}",
    ]
    assert len(lines) == 5
    checkpoint_uid = lines[2].removeprefix("CHECKPOINT · ")
    assert str(uuid.UUID(checkpoint_uid)) == checkpoint_uid
    assert lines[3] == (f"REVIEW · mem review resolve --receipt {checkpoint_uid}")
    assert lines[4] == "RECOVERY · mem undo"


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

    @staticmethod
    def _issues(*, assumptions: list[str] | None = None) -> list[dict[str, object]]:
        return [
            {
                "issue_id": "schedule-scope",
                "kind": "TEMPORAL",
                "memory_ids": ["m1", "m2"],
                "selected_interpretation": (
                    "The two opening times apply to different day scopes."
                ),
                "basis_ids": ["m1", "m2"],
                "assumptions": assumptions or [],
                "reason": "Explicit day scope makes the complete schedule coherent.",
            }
        ]

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.operations.append(operation)
        if operation == "fit_propositions":
            return json.dumps(self._fit(prompt, initial_verdict=self.initial_verdict))
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
                            "classification": "EXACT_GROUNDING",
                            "resolution_level": "YES",
                            "rule_ids": ["R04_EXACT_GROUNDING"],
                            "issues": self._issues(),
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


class ResolveFindingFixtureProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "find_conflicts":
            self.operations.append(operation)
            payload = json.loads(prompt.split(QUALITY_FIND_MARKER, 1)[1])
            return json.dumps(
                {
                    "findings": [
                        {
                            "pair_id": payload["pairs"][0]["pair_id"],
                            "conflict": "YES",
                            "reason": "The schedules state incompatible times.",
                            "question": "Which schedule is authoritative?",
                        }
                    ]
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolvePostMayProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            result = json.loads(
                super().complete(
                    prompt,
                    operation=operation,
                    output_schema=output_schema,
                )
            )
            candidate = result["candidates"][0]
            candidate["classification"] = "SAFE_ALTERNATIVE"
            candidate["resolution_level"] = "MAY"
            candidate["rule_ids"] = ["R05_SAFE_ALTERNATIVE"]
            return json.dumps(result)
        if operation != "fit_propositions":
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )
        self.operations.append(operation)
        result = self._fit(prompt, initial_verdict="NO")
        for judgment in result["judgments"]:
            if judgment["question_id"] == "resolve-initial":
                continue
            aliases = judgment["considered_proposition_ids"]
            judgment.update(
                verdict="MAY",
                reason="The exact applicability remains an explicit alternative.",
                material_proposition_ids=aliases,
                consistent_reading="Either recorded alternative may apply.",
                inconsistent_reading="The applicable alternative remains unknown.",
            )
        return json.dumps(result)


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
                "question": "Use the automatic information-preserving plan?",
                "candidates": [
                    {
                        "summary": "Add a shared schedule qualification.",
                        "classification": "MINIMUM_REPAIR",
                        "resolution_level": "YES",
                        "rule_ids": ["R01_WHOLE_FRAME"],
                        "issues": self._issues(),
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
                        "classification": "EXACT_GROUNDING",
                        "resolution_level": "YES",
                        "rule_ids": ["R04_EXACT_GROUNDING"],
                        "issues": self._issues(),
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


class ResolveAssumptionProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            self.operations.append(operation)
            return json.dumps(
                {
                    "question": "Continue with the most ordinary working reading?",
                    "candidates": [
                        {
                            "summary": "Treat the second time as a weekend schedule.",
                            "classification": "MINIMUM_REPAIR",
                            "resolution_level": "MAY",
                            "rule_ids": ["R06_NO_INVENTED_DISCRIMINATOR"],
                            "issues": self._issues(
                                assumptions=[
                                    "The 9 o'clock schedule applies on weekends."
                                ]
                            ),
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": (
                                        "The office opens at 9 on weekends."
                                    ),
                                    "source_ids": ["m1", "m2"],
                                    "reason": (
                                        "This is the selected working interpretation."
                                    ),
                                }
                            ],
                        }
                    ],
                }
            )
        if operation == "resolve_candidate_verification":
            self.operations.append(operation)
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": False,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": (
                                "The weekend scope is reasonable but not stated."
                            ),
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveFrameRecordingProvider(ResolveFixtureProvider):
    def __init__(self) -> None:
        super().__init__()
        self.exposures: list[tuple[str, tuple[str, ...]]] = []
        self.rulesets: list[tuple[str, object]] = []
        self.schemas: list[tuple[str, object]] = []

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        self.schemas.append((operation, output_schema))
        if operation == "fit_propositions":
            payload = json.loads(prompt.split(FIT_MARKER, 1)[1])
            aliases = tuple(
                proposition["proposition_id"]
                for proposition in payload["questions"][0]["propositions"]
            )
        elif operation == "resolve_candidates":
            payload = json.loads(prompt.split(RESOLVE_MARKER, 1)[1])
            aliases = tuple(memory["memory_id"] for memory in payload["memories"])
            self.rulesets.append((operation, payload["ruleset"]))
        elif operation == "resolve_candidate_verification":
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            aliases = tuple(
                memory["memory_id"] for memory in payload["original_memories"]
            )
            self.rulesets.append((operation, payload["ruleset"]))
        else:  # pragma: no cover - fixture guards the operation catalog.
            aliases = ()
        self.exposures.append((operation, aliases))
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveNoPlanProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            self.operations.append(operation)
            return json.dumps(
                {
                    "question": "Which opening time has the narrower scope?",
                    "candidates": [],
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveUngroundedWithoutAssumptionProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidate_verification":
            self.operations.append(operation)
            payload = json.loads(prompt.split(VERIFY_MARKER, 1)[1])
            return json.dumps(
                {
                    "reviews": [
                        {
                            "candidate_id": candidate["candidate_id"],
                            "grounded": False,
                            "preserves_information": True,
                            "delete_justified": True,
                            "reason": "The proposed weekend scope is not supplied.",
                        }
                        for candidate in payload["candidates"]
                    ]
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveDeleteAssumptionProvider(ResolveAssumptionProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            self.operations.append(operation)
            return json.dumps(
                {
                    "question": "Is the 9 o'clock statement obsolete?",
                    "candidates": [
                        {
                            "summary": "Retire the presumed obsolete statement.",
                            "classification": "MINIMUM_REPAIR",
                            "resolution_level": "MAY",
                            "rule_ids": ["R10_NO_DELETE_FOR_FIT"],
                            "issues": self._issues(
                                assumptions=["The 9 o'clock statement is obsolete."]
                            ),
                            "effects": [
                                {
                                    "kind": "DELETE",
                                    "target_id": "m2",
                                    "new_content": "",
                                    "source_ids": ["m2"],
                                    "reason": "The working interpretation retires it.",
                                }
                            ],
                        }
                    ],
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveOutsideIssueProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            self.operations.append(operation)
            issue = self._issues()[0]
            issue["memory_ids"] = ["m1"]
            return json.dumps(
                {
                    "question": "Use the scoped schedule?",
                    "candidates": [
                        {
                            "summary": "Scope the second schedule.",
                            "classification": "EXACT_GROUNDING",
                            "resolution_level": "YES",
                            "rule_ids": ["R04_EXACT_GROUNDING"],
                            "issues": [issue],
                            "effects": [
                                {
                                    "kind": "UPDATE",
                                    "target_id": "m2",
                                    "new_content": (
                                        "The office opens at 9 on weekends."
                                    ),
                                    "source_ids": ["m1", "m2"],
                                    "reason": "The weekend scope separates the times.",
                                }
                            ],
                        }
                    ],
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
        )


class ResolveMultiplePlanProvider(ResolveFixtureProvider):
    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        if operation == "resolve_candidates":
            self.operations.append(operation)
            plan = {
                "summary": "Scope the second schedule.",
                "classification": "EXACT_GROUNDING",
                "resolution_level": "YES",
                "rule_ids": ["R04_EXACT_GROUNDING"],
                "issues": self._issues(),
                "effects": [
                    {
                        "kind": "UPDATE",
                        "target_id": "m2",
                        "new_content": "The office opens at 9 on weekends.",
                        "source_ids": ["m1", "m2"],
                        "reason": "The weekend scope separates the times.",
                    }
                ],
            }
            return json.dumps(
                {
                    "question": "Use one automatic plan?",
                    "candidates": [plan, plan],
                }
            )
        return super().complete(
            prompt,
            operation=operation,
            output_schema=output_schema,
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
    assert checkpoints[0]["args"]["issues"][0]["uid"] == "schedule-scope"
    assert checkpoints[0]["args"]["issues"][0]["assumptions"] == []


def test_resolve_already_fit_stops_after_independent_initial_fit(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolveFixtureProvider(initial_verdict="YES")

    analysis, _port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "ALREADY_FIT"
    assert not analysis.candidates
    assert provider.operations == ["fit_propositions"]


def test_resolve_every_semantic_turn_reads_the_complete_frozen_frame(
    isolated_store,
):
    store = MemoryStore()
    _context(store, third=True)
    provider = ResolveFrameRecordingProvider()

    analysis, _port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "PROPOSAL"
    assert provider.exposures == [
        ("fit_propositions", ("m1", "m2", "m3")),
        ("resolve_candidates", ("m1", "m2", "m3")),
        ("resolve_candidate_verification", ("m1", "m2", "m3")),
        ("fit_propositions", ("m1", "m2", "m3")),
    ]
    exact_ruleset = resolve_ruleset_prompt_payload()
    assert provider.rulesets == [
        ("resolve_candidates", exact_ruleset),
        ("resolve_candidate_verification", exact_ruleset),
    ]
    generation_schema = dict(provider.schemas)["resolve_candidates"]
    assert "uniqueItems" not in json.dumps(generation_schema)


def test_default_resolve_accepts_independently_verified_post_fit_may(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolvePostMayProvider()

    analysis, port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "PROPOSAL"
    assert analysis.frame.request.target_fit == "MAY"
    assert analysis.candidates[0].resolution_level == "MAY"
    assert analysis.candidates[0].fit.verdict == "MAY"
    receipt = apply_resolve(
        analysis,
        analysis.candidates[0].uid,
        frame_port=port,
    )
    assert receipt.updated_uids
    assert len(store.list_checkpoints("resolve/test")) == 1


def test_strict_yes_target_rejects_a_post_fit_may_plan(isolated_store):
    store = MemoryStore()
    _context(store)

    analysis, _port = _run(
        store,
        ResolvePostMayProvider(),
        ResolveRequest("resolve/test", target_fit="YES"),
    )

    assert analysis.status == "NEEDS_INPUT"
    assert analysis.frame.request.target_fit == "YES"
    assert not analysis.candidates


def test_resolve_assumption_is_a_read_only_working_interpretation(isolated_store):
    store = MemoryStore()
    _context(store)
    before = store.load_direct("resolve/test").to_dict()

    analysis, port = _run(
        store,
        ResolveAssumptionProvider(),
        ResolveRequest("resolve/test"),
    )

    assert analysis.status == "ASSUMED"
    assert len(analysis.candidates) == 1
    candidate = analysis.candidates[0]
    assert candidate.grounded is False
    assert candidate.issues[0].assumptions == (
        "The 9 o'clock schedule applies on weekends.",
    )
    with pytest.raises(ResolveError, match="process-local"):
        apply_resolve(analysis, candidate.uid, frame_port=port)
    assert store.load_direct("resolve/test").to_dict() == before
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_no_reasonable_interpretation_requests_input(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolveNoPlanProvider()

    analysis, _port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "NEEDS_INPUT"
    assert not analysis.candidates
    assert provider.operations == ["fit_propositions", "resolve_candidates"]


def test_resolve_ungrounded_plan_without_named_assumption_is_rejected(
    isolated_store,
):
    store = MemoryStore()
    _context(store)
    provider = ResolveUngroundedWithoutAssumptionProvider()

    analysis, _port = _run(store, provider, ResolveRequest("resolve/test"))

    assert analysis.status == "NEEDS_INPUT"
    assert not analysis.candidates
    assert provider.operations == [
        "fit_propositions",
        "resolve_candidates",
        "resolve_candidate_verification",
    ]


def test_resolve_never_carries_an_assumed_delete_forward(isolated_store):
    store = MemoryStore()
    _context(store)
    before = store.load_direct("resolve/test").to_dict()
    provider = ResolveDeleteAssumptionProvider()

    analysis, _port = _run(
        store,
        provider,
        ResolveRequest(
            "resolve/test",
            allow_delete=True,
            guidance="Deletion is allowed only if obsolescence is grounded.",
        ),
    )

    assert analysis.status == "NEEDS_INPUT"
    assert not analysis.candidates
    assert store.load_direct("resolve/test").to_dict() == before
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_rejects_an_edit_outside_its_reported_issue(isolated_store):
    store = MemoryStore()
    _context(store)

    with pytest.raises(ResolveError, match="outside its reported Issues"):
        _run(
            store,
            ResolveOutsideIssueProvider(),
            ResolveRequest("resolve/test"),
        )


def test_resolve_rejects_multiple_model_authored_plans(isolated_store):
    store = MemoryStore()
    _context(store)

    with pytest.raises(ResolveError, match="invalid candidate list"):
        _run(
            store,
            ResolveMultiplePlanProvider(),
            ResolveRequest("resolve/test"),
        )


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


def test_resolve_finding_source_mismatch_fails_before_provider_connection(
    isolated_store,
):
    store = MemoryStore()
    context, first, second = _context(store)

    class ForbiddenProviderFactory:
        def __call__(self):
            raise AssertionError("provider must not connect for stale finding evidence")

    request = ResolveRequest(
        context.name,
        memory_selectors=(first.uid, second.uid),
        source_precondition=ResolveSourcePrecondition(
            context_uid=context.uid,
            display_name=context.name,
            direct_memory_digest="0" * 64,
        ),
    )
    port = MemoryStoreResolvePort(store, current_name=context.name)

    with pytest.raises(ResolveConflictError, match="finding source"):
        run_resolve(
            request,
            frame_port=port,
            semantic_port=ProviderResolveSemanticPort(),
            provider_factory=ForbiddenProviderFactory(),
        )


def test_resolve_accepts_matching_finding_source_precondition(isolated_store):
    store = MemoryStore()
    context, first, second = _context(store)
    provider = ResolveFixtureProvider(initial_verdict="YES")

    analysis, _port = _run(
        store,
        provider,
        ResolveRequest(
            context.name,
            memory_selectors=(first.uid, second.uid),
            source_precondition=ResolveSourcePrecondition(
                context_uid=context.uid,
                display_name=context.name,
                direct_memory_digest=direct_context_digest(context),
            ),
        ),
    )

    assert analysis.status == "ALREADY_FIT"
    assert provider.operations == ["fit_propositions"]


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


def test_resolve_create_is_an_ordinary_information_preserving_effect(isolated_store):
    store = MemoryStore()
    _context(store)
    analysis, port = _run(
        store,
        ResolveFixtureProvider(effect_kind="CREATE"),
        ResolveRequest("resolve/test"),
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


def test_resolve_create_can_be_explicitly_disabled() -> None:
    assert ResolveRequest("resolve/test", allow_create=False).requested_effects == (
        "UPDATE",
    )


def test_resolve_returns_one_automatic_information_preserving_plan(
    isolated_store,
):
    store = MemoryStore()
    _context(store)

    analysis, _port = _run(
        store,
        ResolveChoiceProvider(),
        ResolveRequest("resolve/test"),
    )

    assert analysis.status == "PROPOSAL"
    assert len(analysis.candidates) == 1
    assert analysis.candidates[0].effects[0].kind == "CREATE"
    assert analysis.candidates[0].issues[0].uid == "schedule-scope"


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


def test_resolve_tui_projects_and_applies_the_preselected_automatic_plan(
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
        # The verified plan is already selected. Move to its separated Apply
        # row and activate it with the same Enter-only compact grammar as Meld.
        pipe_input.send_text("\x1b[B\r")
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


def test_resolve_tui_assumed_interpretation_is_read_only(isolated_store):
    store = MemoryStore()
    _context(store)
    analysis, _port = _run(
        store,
        ResolveAssumptionProvider(),
        ResolveRequest("resolve/test"),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        receipt = run_resolve_tui(
            analysis,
            apply_candidate=lambda _candidate_uid: pytest.fail(
                "an assumed Resolve interpretation must not expose Apply"
            ),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert receipt is None
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_plain_cli_automatically_applies_one_grounded_plan(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test"],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)
    assert len(store.list_checkpoints("resolve/test")) == 1
    assert provider.operations == [
        "fit_propositions",
        "resolve_candidates",
        "resolve_candidate_verification",
        "fit_propositions",
    ]


def test_resolve_plain_cli_reports_applied_post_fit_may(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        ResolvePostMayProvider,
    )

    result = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test"],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result, fit_verdict="MAY")


def test_resolve_plain_cli_compacts_needs_input_without_a_repair_report(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        ResolveNoPlanProvider,
    )

    result = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        "RESOLVE · resolve/test\n"
        "NEEDS INPUT · Which opening time has the narrower scope?\n"
    )
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_plain_cli_retains_assumption_boundary_compactly(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        ResolveAssumptionProvider,
    )

    result = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        "RESOLVE · resolve/test\n"
        "TEMPORARY INTERPRETATION · Treat the second time as a weekend schedule.\n"
        "ASSUMPTION · The 9 o'clock schedule applies on weekends.\n"
        "NEEDS INPUT · Continue with the most ordinary working reading?\n"
        "NO CHANGE · Grounding is required before Apply\n"
    )
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_plain_cli_reports_actual_already_fit_may_verdict(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    provider = ResolveNoPlanProvider(initial_verdict="MAY")
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["resolve", "--context", "resolve/test"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == ("RESOLVE · resolve/test\nFIT · MAY · NO CHANGE\n")
    assert store.list_checkpoints("resolve/test") == []


def test_resolve_plain_cli_compacts_all_applied_effect_counts(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        ResolveIntegratedEffectsProvider,
    )

    result = runner.invoke(
        app,
        [
            "resolve",
            "--context",
            "resolve/test",
            "--allow-delete",
            "--guidance",
            "The unscoped statement is obsolete after integration.",
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(
        result,
        effects="CREATE 1 · UPDATE 1 · DELETE 1",
    )


def test_resolve_plain_cli_auto_classifies_positional_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, _second = _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(app, ["resolve", context.name])

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)
    assert len(store.list_checkpoints(context.name)) == 1


def test_resolve_plain_cli_mixes_context_and_memory_auto_operands(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, second = _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        ["resolve", second.uid[:8], context.name],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)
    assert len(store.list_checkpoints(context.name)) == 1


def test_resolve_plain_cli_finds_unique_owner_for_bare_memory_operand(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, second = _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    assert store.current_context_name() is None
    result = runner.invoke(app, ["resolve", second.uid[:8]])

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)
    assert len(store.list_checkpoints(context.name)) == 1


def test_resolve_plain_cli_accepts_explicit_short_memory_operand(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, second = _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "resolve",
            context.name,
            "--memory",
            second.uid[:6],
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)


def test_resolve_plain_cli_combines_same_explicit_and_qualified_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, second = _context(store)
    provider = ResolveFixtureProvider()
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        lambda: provider,
    )

    result = runner.invoke(
        app,
        [
            "resolve",
            f"{context.name}:{second.uid[:8]}",
            "--context",
            context.name,
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_compact_applied_receipt(result)


def test_resolve_cli_rejects_distinct_context_operands_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, _second = _context(store)
    other = ops.init("resolve/other")
    other_memory = ops.add(other, "The office opens at 10.")
    ops.add(other, "The office opens at 11.")
    store.save(other)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return ResolveFixtureProvider()

    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        provider_factory,
    )

    result = runner.invoke(
        app,
        [
            "resolve",
            context.name,
            f"{other.name}:{other_memory.uid[:8]}",
        ],
    )

    assert result.exit_code == 1
    assert "select multiple Contexts" in result.stderr
    assert "resolve/test" in result.stderr
    assert "resolve/other" in result.stderr
    assert calls == 0


def test_resolve_cli_rejects_two_prefixes_for_same_memory_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    context, _first, second = _context(store)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return ResolveFixtureProvider()

    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        provider_factory,
    )

    result = runner.invoke(
        app,
        [
            "resolve",
            context.name,
            second.uid[:8],
            second.uid[:12],
        ],
    )

    assert result.exit_code == 1
    assert "selectors repeat Memory" in result.stderr
    assert calls == 0


def test_resolve_help_exposes_mixed_context_memory_operands() -> None:
    result = runner.invoke(app, ["resolve", "--help"])

    assert result.exit_code == 0, result.output
    assert "Auto operand" in result.output
    assert "--memory" in result.output


def test_resolve_plain_cli_can_replay_an_external_exact_plan(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    _context(store)
    analysis, _port = _run(
        store,
        ResolveFixtureProvider(),
        ResolveRequest("resolve/test"),
    )
    monkeypatch.setattr(
        resolve_command,
        "connect_semantic_provider",
        ResolveFixtureProvider,
    )

    applied = runner.invoke(
        app,
        [
            "resolve",
            "--context",
            "resolve/test",
            "--candidate",
            analysis.candidates[0].uid,
            "--expected-revision",
            analysis.frame.revision,
            "--apply",
        ],
    )

    assert applied.exit_code == 0, applied.output
    _assert_compact_applied_receipt(applied)
    assert len(store.list_checkpoints("resolve/test")) == 1


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
    assert analysis.target_fit == "MAY"
    assert analysis.requested_effects == ("UPDATE", "CREATE")
    assert analysis.candidates[0].grounded is True
    assert analysis.candidates[0].resolution_level == "YES"
    assert analysis.candidates[0].fit_verdict == "YES"
    assert analysis.candidates[0].issues[0].kind == "TEMPORAL"
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


def test_resolve_agent_analyzes_then_applies_the_cached_exact_plan(isolated_store):
    store = MemoryStore()
    _context(store)
    provider = ResolveFixtureProvider()
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=lambda: provider,
        )
    )
    request = {
        "version": RESOLVE_AGENT_CONTRACT_VERSION,
        "kind": "analyze",
        "context_name": "resolve/test",
    }

    preview = registry.invoke(RESOLVE_AGENT_TOOL_NAME, request)
    candidate_uid = preview["result"]["candidates"][0]["uid"]
    revision = preview["result"]["revision"]
    operations_after_analysis = tuple(provider.operations)
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
    assert preview["version"] == RESOLVE_AGENT_CONTRACT_VERSION
    assert preview["result"]["effect"] == "NONE"
    assert preview["result"]["target_fit"] == "MAY"
    assert preview["result"]["candidates"][0]["grounded"] is True
    assert preview["result"]["candidates"][0]["fit_verdict"] == "YES"
    assert preview["result"]["candidates"][0]["issues"][0]["uid"] == ("schedule-scope")
    assert receipt["ok"] is True
    assert tuple(provider.operations) == operations_after_analysis
    assert receipt["result"]["effect"] == "CHECKPOINT"
    assert receipt["result"]["candidate_uid"] == candidate_uid


def test_resolve_agent_carries_assumed_plan_without_replaying_or_applying(
    isolated_store,
):
    store = MemoryStore()
    _context(store)
    provider = ResolveAssumptionProvider()
    registry = build_default_agent_tool_registry(
        MemCommitClient(
            root=isolated_store,
            semantic_provider_factory=lambda: provider,
        )
    )
    request = {
        "version": RESOLVE_AGENT_CONTRACT_VERSION,
        "kind": "analyze",
        "context_name": "resolve/test",
    }

    preview = registry.invoke(RESOLVE_AGENT_TOOL_NAME, request)
    operations_after_analysis = tuple(provider.operations)
    candidate = preview["result"]["candidates"][0]
    blocked = registry.invoke(
        RESOLVE_AGENT_TOOL_NAME,
        {
            **request,
            "kind": "apply",
            "candidate_uid": candidate["uid"],
            "expected_revision": preview["result"]["revision"],
        },
    )

    assert preview["result"]["status"] == "ASSUMED"
    assert candidate["grounded"] is False
    assert candidate["issues"][0]["assumptions"]
    assert blocked["ok"] is False
    assert blocked["error"]["code"] == "invalid_request"
    assert "cannot be applied" in blocked["error"]["message"]
    assert tuple(provider.operations) == operations_after_analysis
    assert store.list_checkpoints("resolve/test") == []


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
        ("READ", "UPDATE"),
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
    assert (
        authority_store.load_direct("schedule")
        .memories[receipt.updated_uids[0]]
        .content
        == "The office opens at 9 on weekends."
    )


def test_granted_finding_handoff_reauthorizes_requested_effects(
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
    provider = ResolveFindingFixtureProvider()
    client = MemCommitClient(semantic_provider_factory=lambda: provider)

    finding = client.find_conflicts(("shared/schedule",)).handoffs[0]
    analysis = client.resolve_conflict_finding(finding, allow_create=True)

    assert finding.sources[0].display_name == "shared/schedule"
    assert analysis.requested_effects == ("UPDATE", "CREATE")
    assert analysis.allowed_effects == ("UPDATE",)
    assert analysis.denied_effects == ("CREATE",)
    assert provider.operations[0] == "find_conflicts"


def test_granted_resolve_uses_read_and_requested_update_authority(
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

    result = MemCommitClient(
        semantic_provider_factory=provider,
    ).resolve_context("shared/schedule")

    assert result.status == "PROPOSAL"
    assert result.allowed_effects == ("UPDATE",)
    assert calls == 1


def test_explicit_root_resolve_does_not_inherit_host_grants(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _granted_resolve_fixture(
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
        ("READ", "UPDATE"),
    )
    client = MemCommitClient(
        semantic_provider_factory=ResolveFixtureProvider,
    )
    analysis = client.resolve_context("shared/schedule")
    before = authority_store.load_direct("schedule").to_dict()

    update_authority_grant(grant.uid, permissions=("READ",))

    with pytest.raises(SemanticAuthorityError):
        client.apply_resolve(
            analysis,
            candidate_uid=analysis.candidates[0].uid,
        )
    assert authority_store.load_direct("schedule").to_dict() == before
