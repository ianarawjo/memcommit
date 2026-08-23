"""Exact destination-context behavior for ambient Elaborate generation."""

from __future__ import annotations

import json
import uuid

import pytest

import memcommit.ops as ops
from memcommit.authority.access import granted_context_link, resolve_context_access
from memcommit.context import Context, QueryContextRef
from memcommit.elaborate import ELABORATE_PAYLOAD_MARKER, ElaborateError
from memcommit.elaborate_add_runtime import (
    apply_prepared_elaborate_add,
    freeze_elaborate_context_source,
    prepare_elaborate_add,
)
from memcommit.ground_elaborate import (
    execute_ground_elaborate,
    freeze_ground_elaborate,
)
from memcommit.ground_workspace_application import (
    AddGroundWorkspaceMemoryRequest,
    CreateGroundWorkspaceRequest,
)
from memcommit.ground_workspace_runtime import (
    execute_ground_workspace_creation,
    execute_ground_workspace_memory_add,
)
from memcommit.interfaces.cli.elaborate import elaborate_result_text
from memcommit.interfaces.tui.operations.elaborate import project_elaborate_result
from memcommit.profile_config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.profiles import create_authority_grant, update_authority_grant
from memcommit.store import MemoryStore, context_record_digest
from tests.elaborate_validation_support import (
    passing_elaborate_validation_response,
)


class TargetAwareProvider:
    def __init__(self):
        self.payloads: list[dict[str, object]] = []

    def complete(self, prompt, *, operation, output_schema=None):
        validation = passing_elaborate_validation_response(prompt, operation)
        if validation is not None:
            return validation
        payload = json.loads(prompt.split(ELABORATE_PAYLOAD_MARKER, 1)[1])
        self.payloads.append(payload)
        target = payload.get("target_context")
        refs = []
        if isinstance(target, dict):
            refs = [
                item["target_id"]
                for item in target["items"]
                if item["kind"] == "MEMORY"
            ]
        target_field = (
            {"target_context_refs": refs} if target is not None else {}
        )
        if payload["mode"] == "GOAL_TO_RULES":
            return json.dumps(
                {
                    "overview": "The Goal is made operational in the Target's form.",
                    "rules": [
                        {
                            "content": "Confirm the selected value before acting.",
                            "rationale": "This makes the Goal reviewable.",
                            **target_field,
                        }
                    ],
                }
            )
        return json.dumps(
            {
                "overview": "One complete Case follows every current Rule.",
                "cases": [
                    {
                        "proposition": (
                            "A person confirms option B, and the system acts on "
                            "option B only after that confirmation."
                        ),
                        "expected": "Act on option B.",
                        "rationale": "The Case preserves the established Target form.",
                        "case_role": "FIT",
                        "rule_checks": [
                            {
                                "source_rule_index": index,
                                "evidence": "The Case visibly follows this Rule.",
                            }
                            for index, _rule in enumerate(payload["inputs"], 1)
                        ],
                        **target_field,
                    }
                ],
            }
        )


def _context(store: MemoryStore, name: str, *contents: str) -> Context:
    context = ops.init(name)
    for content in contents:
        ops.add(context, content)
    store.create_context(context)
    return context


def test_target_ambient_follows_local_embeds_deduplicates_cycles_and_keeps_query_name_only(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = _context(store, "ambient/source", "Act only after confirmation.")
    target = ops.init("ambient/target")
    direct = ops.add(target, "A person confirms option A before the system acts.")
    target.add(
        QueryContextRef(
            uid="00000000-0000-4000-8000-000000000711",
            name="private/preferences",
            target_source_uid="00000000-0000-4000-8000-000000000712",
            provider="test-query",
        )
    )
    child = ops.init("ambient/examples")
    child_memory = ops.add(
        child,
        "A person declines option C, and the system leaves the choice unchanged.",
    )
    # The reverse pointer makes a real persisted cycle. Target traversal must
    # terminate by Context identity without dropping the child's one Memory.
    child.add(Context(uid=target.uid, name=target.name))
    store.create_context(child)
    target.add(child)
    store.create_context(target)
    unrelated = _context(store, "ambient/unrelated", "NEVER DISCLOSE THIS MEMORY")
    frozen_source = freeze_elaborate_context_source(
        store,
        context_name=source.name,
        role="rules",
        number=1,
    )
    source_digest = context_record_digest(store.load_direct(source.name))
    provider = TargetAwareProvider()

    prepared = prepare_elaborate_add(
        store=store,
        request=frozen_source.request,
        target_name=target.name,
        source=frozen_source,
        provider_factory=lambda: provider,
    )

    payload = provider.payloads[0]
    ambient = payload["target_context"]
    assert ambient["name"] == target.name
    assert ambient["role"] == "AMBIENT_DESTINATION_CONTEXT"
    assert ambient["items"] == [
        {
            "target_id": "t1",
            "kind": "MEMORY",
            "context": target.name,
            "content": direct.content,
        },
        {
            "target_id": "t2",
            "kind": "QUERY_ONLY_CONTEXT",
            "context": "private/preferences",
        },
        {
            "target_id": "t3",
            "kind": "MEMORY",
            "context": child.name,
            "content": child_memory.content,
        },
    ]
    assert unrelated.memories[next(iter(unrelated.memories))].content not in json.dumps(
        payload
    )
    assert prepared.result.analysis.cases[0].target_context_refs == ("t1", "t3")
    assert tuple(
        binding.context_name for binding in prepared.target_context.local_contexts
    ) == (target.name, child.name)
    plain = elaborate_result_text(prepared.result)
    rendered = "".join(
        text
        for _style, text in project_elaborate_result(prepared.result).render(
            focused_uid="ELABORATE:TARGET"
        )
    )
    assert "TARGET AMBIENT · ambient/target · 3 ITEMS" in plain
    assert "t2 · QUERY ONLY · private/preferences · NAME ONLY" in plain
    assert "TARGET USED · t1, t3" in plain
    assert "TARGET AMBIENT · ambient/target · 3 ITEMS" in rendered

    receipt = apply_prepared_elaborate_add(prepared, store=store)
    assert receipt.count == 1
    assert len(store.load_direct(target.name).order) == 4
    assert context_record_digest(store.load_direct(source.name)) == source_digest
    checkpoint = store.list_checkpoints(target.name)[0]
    elaborate_receipt = checkpoint["args"]["elaborate"]
    assert elaborate_receipt["version"] == 3
    assert elaborate_receipt["case_validation"] == (
        "INDEPENDENT_SOURCE_RULE_CONFORMANCE_AND_SOURCE_FIT"
    )
    assert elaborate_receipt["target_ambient"]["name"] == target.name
    assert elaborate_receipt["proposals"][0]["target_context_refs"] == ["t1", "t3"]
    assert elaborate_receipt["proposals"][0]["validation"]["source_fit"] == "YES"


def test_same_context_source_wins_and_is_not_resent_as_target_ambient(
    isolated_store,
) -> None:
    store = MemoryStore()
    current = _context(store, "ambient/same", "Act only after confirmation.")
    source = freeze_elaborate_context_source(
        store,
        context_name=current.name,
        role="rules",
        number=1,
    )
    provider = TargetAwareProvider()

    prepared = prepare_elaborate_add(
        store=store,
        request=source.request,
        target_name=current.name,
        source=source,
        provider_factory=lambda: provider,
    )

    assert "target_context" not in provider.payloads[0]
    assert prepared.result.analysis.target_context is None
    assert prepared.target_context.excluded_root_memory_uids == source.memory_uids


def test_embedded_target_drift_fails_after_provider_without_partial_add(
    isolated_store,
) -> None:
    store = MemoryStore()
    source = _context(store, "ambient/drift-source", "Act only after confirmation.")
    child = _context(store, "ambient/drift-child", "Prior compliant example.")
    target = ops.init("ambient/drift-target")
    target.add(child)
    store.create_context(target)
    frozen_source = freeze_elaborate_context_source(
        store,
        context_name=source.name,
        role="rules",
        number=1,
    )

    class DriftingProvider(TargetAwareProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            changed = store.load_for_update(child.name)
            changed.add("Concurrent embedded example.")
            store.save(changed)
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    provider = DriftingProvider()
    with pytest.raises(ElaborateError, match="Target ambient Context.*changed"):
        prepare_elaborate_add(
            store=store,
            request=frozen_source.request,
            target_name=target.name,
            source=frozen_source,
            provider_factory=lambda: provider,
        )

    assert len(provider.payloads) == 1
    assert tuple(store.load_direct(target.name).iter_items())[-1].uid == child.uid


def test_physical_ground_uses_only_the_existing_destination_lane_as_ambient(
    isolated_store,
) -> None:
    store = MemoryStore()
    execute_ground_workspace_creation(
        CreateGroundWorkspaceRequest(name="ambient-ground"),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="ambient-ground",
            lane="rules",
            content="Act only after explicit confirmation.",
        ),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="ambient-ground",
            lane="examples",
            content="A person confirms option A before the system acts.",
        ),
        store=store,
    )
    execute_ground_workspace_memory_add(
        AddGroundWorkspaceMemoryRequest(
            workspace_name="ambient-ground",
            lane="contexts",
            content="THIS OTHER LANE MUST NOT ENTER THE PROMPT.",
        ),
        store=store,
    )
    frozen = freeze_ground_elaborate(
        store,
        ground_name="ambient-ground",
        direction="RULES_TO_CASES",
        number=1,
    )
    provider = TargetAwareProvider()

    result = execute_ground_elaborate(
        frozen,
        store=store,
        provider_factory=lambda: provider,
    )

    payload = provider.payloads[0]
    assert payload["target_context"]["name"] == "ambient-ground/examples"
    assert [
        item["content"] for item in payload["target_context"]["items"]
    ] == ["A person confirms option A before the system acts."]
    assert "THIS OTHER LANE" not in json.dumps(payload)
    assert result.elaborate.analysis.cases[0].target_context_refs == ("t1",)


def test_granted_embed_requires_read_embed_derive_and_combine_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    store = MemoryStore()
    source = _context(store, "grant/source", "Act only after confirmation.")
    target = _context(store, "grant/target")
    store.set_current(target.name)
    grantee = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="ambient-authority",
        kind="MANAGED",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    advisor = ops.init("advisor/examples")
    advice = ops.add(advisor, "A prior authority example preserves this exact form.")
    authority_store.save(advisor)
    registry = ProfileRegistry(
        generation=1,
        active_uid=grantee.uid,
        profiles=(grantee, authority),
        grants=(),
    )
    registry_path = profile_registry_file()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=grantee.name,
        resource_name=advisor.name,
        attachment_name=target.name,
        public_name="shared/advisor-examples",
        permissions=("READ", "EMBED", "DERIVE", "COMBINE"),
    )
    access = resolve_context_access(
        store,
        "shared/advisor-examples",
        current_name=target.name,
        required_permission="READ",
    )
    embedded = Context(uid=advisor.uid, name="shared/advisor-examples")
    embedded._granted_link = granted_context_link(access, context_uid=advisor.uid)
    updated_target = store.load_for_update(target.name)
    updated_target.add(embedded)
    store.save(updated_target)
    frozen_source = freeze_elaborate_context_source(
        store,
        context_name=source.name,
        role="rules",
        number=1,
    )
    provider = TargetAwareProvider()

    prepared = prepare_elaborate_add(
        store=store,
        request=frozen_source.request,
        target_name=target.name,
        source=frozen_source,
        provider_factory=lambda: provider,
    )

    assert provider.payloads[0]["target_context"]["items"] == [
        {
            "target_id": "t1",
            "kind": "MEMORY",
            "context": "shared/advisor-examples",
            "content": advice.content,
        }
    ]
    assert prepared.result.analysis.cases[0].target_context_refs == ("t1",)
    with pytest.raises(ElaborateError, match="EXPORT.*SAVE_ANALYSIS"):
        apply_prepared_elaborate_add(prepared, store=store)
    assert len(store.load_direct(target.name).order) == 1

    preflight_provider = TargetAwareProvider()
    with pytest.raises(ElaborateError, match="EXPORT.*SAVE_ANALYSIS"):
        prepare_elaborate_add(
            store=store,
            request=frozen_source.request,
            target_name=target.name,
            source=frozen_source,
            provider_factory=lambda: preflight_provider,
            will_apply=True,
        )
    assert preflight_provider.payloads == []

    update_authority_grant(
        grant.uid,
        permissions=(
            "READ",
            "EMBED",
            "DERIVE",
            "COMBINE",
            "EXPORT",
            "SAVE_ANALYSIS",
        ),
    )
    add_provider = TargetAwareProvider()
    addable = prepare_elaborate_add(
        store=store,
        request=frozen_source.request,
        target_name=target.name,
        source=frozen_source,
        provider_factory=lambda: add_provider,
        will_apply=True,
    )
    assert apply_prepared_elaborate_add(addable, store=store).count == 1

    update_authority_grant(grant.uid, permissions=("READ", "EMBED"))
    blocked_provider = TargetAwareProvider()
    with pytest.raises(ElaborateError, match="COMBINE.*DERIVE"):
        prepare_elaborate_add(
            store=store,
            request=frozen_source.request,
            target_name=target.name,
            source=frozen_source,
            provider_factory=lambda: blocked_provider,
        )
    assert blocked_provider.payloads == []
