"""Stored Memory and Context adapters for general Fit."""

from __future__ import annotations

import json
import uuid

import pytest
from typer.testing import CliRunner

import memcommit.commands.fit.command as fit_command
import memcommit.application.ops as ops
from memcommit.adapters.console.entrypoint import app
from memcommit.context import Context, Memory
from memcommit.application.operations.fit.application import (
    FitMemorySourceRequest,
    FitStoredSourcesRequest,
)
from memcommit.application.operations.fit.judgment import (
    FIT_JUDGMENT_PAYLOAD_MARKER,
    FitProposition,
)
from memcommit.application.operations.fit.runtime import FitSourceError, run_stored_source_fit
from memcommit.application.operations.profile.config import (
    AUTHORING_PROFILE_NAME,
    AUTHORING_PROFILE_UID,
    ProfileEntry,
    ProfileRegistry,
    profile_registry_file,
    profile_store_dir,
)
from memcommit.application.operations.profile.model import (
    ProfileError,
    create_authority_grant,
    update_authority_grant,
)
from memcommit.persistence.store import MemoryStore


class _FitProvider:
    def __init__(self, before_return=None) -> None:
        self.before_return = before_return
        self.payload: dict[str, object] | None = None

    def complete(self, prompt: str, *, operation: str, output_schema=None) -> str:
        assert operation == "fit_propositions"
        assert output_schema is not None
        self.payload = json.loads(prompt.split(FIT_JUDGMENT_PAYLOAD_MARKER, 1)[1])
        question = self.payload["questions"][0]
        aliases = [
            item["proposition_id"]
            for item in (*question["background"], *question["propositions"])
        ]
        if self.before_return is not None:
            self.before_return()
        return json.dumps(
            {
                "overview": "The complete stored set was judged once.",
                "judgments": [
                    {
                        "question_id": "fit",
                        "verdict": "YES",
                        "reason": "The stored claims can jointly hold.",
                        "considered_proposition_ids": aliases,
                        "material_proposition_ids": [],
                        "consistent_reading": "",
                        "inconsistent_reading": "",
                    }
                ],
            }
        )


def _context(store: MemoryStore, name: str, *contents: str):
    context = ops.init(name)
    memories = tuple(ops.add(context, content) for content in contents)
    store.save(context)
    return context, memories


def _seed_legacy_context(store: MemoryStore, context: Context) -> None:
    path = store.contexts_dir.joinpath(*context.name.split("/"), "context.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(context.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _granted_context(tmp_path, monkeypatch, permissions):
    monkeypatch.setenv("HOME", str(tmp_path))
    active_store = MemoryStore()
    attachment, _ = _context(active_store, "fit/attachment")
    active_store.set_current(attachment.name)

    authority = ProfileEntry(
        uid=str(uuid.uuid4()),
        name="fit-authority",
        kind="MANAGED",
    )
    authoring = ProfileEntry(
        uid=AUTHORING_PROFILE_UID,
        name=AUTHORING_PROFILE_NAME,
        kind="AUTHORING",
    )
    authority_store = MemoryStore(root=profile_store_dir(authority))
    source, memories = _context(
        authority_store,
        "fit-source",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )
    registry = ProfileRegistry(
        generation=1,
        active_uid=authoring.uid,
        profiles=(authoring, authority),
    )
    path = profile_registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry.to_dict()) + "\n", encoding="utf-8")
    _registry, grant = create_authority_grant(
        authority_name=authority.name,
        grantee_name=authoring.name,
        resource_name=source.name,
        attachment_name=attachment.name,
        public_name="shared/fit-source",
        permissions=permissions,
    )
    return active_store, source, memories, grant


def test_stored_fit_combines_literal_memory_and_context_sources(isolated_store):
    store = MemoryStore()
    current, current_memories = _context(
        store,
        "work/current",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )
    other, other_memories = _context(
        store,
        "work/other",
        "Staff may use the side entrance.",
    )
    store.set_current(current.name)
    provider = _FitProvider()

    result = run_stored_source_fit(
        FitStoredSourcesRequest(
            propositions=(
                FitProposition("p1", "Visitors use the lobby.", "PROPOSITION"),
            ),
            memory_sources=(FitMemorySourceRequest(current_memories[0].uid[:8]),),
            context_locators=(other.name,),
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.analysis.assessment.verdict == "YES"
    assert [item.alias for item in result.analysis.question.propositions] == [
        "p1",
        "m1",
        "m2",
    ]
    assert [item.content for item in result.analysis.question.propositions] == [
        "Visitors use the lobby.",
        current_memories[0].content,
        other_memories[0].content,
    ]
    assert [item.role for item in result.analysis.question.propositions] == [
        "PROPOSITION",
        "MEMORY",
        "MEMORY",
    ]
    assert [item.kind for item in result.input_origins] == ["MEMORY", "CONTEXT"]
    assert [item.context_name for item in result.input_origins] == [
        current.name,
        other.name,
    ]
    assert [item.memory_uid for item in result.input_origins] == [
        current_memories[0].uid,
        other_memories[0].uid,
    ]


def test_mem_fit_accepts_multiple_current_memory_selectors(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, memories = _context(
        store,
        "fit/current",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        [
            "fit",
            "--memory",
            memories[0].uid[:8],
            "--memory",
            memories[1].uid[:8],
            "--plain",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"FIT · YES · [TARGETS: MEMORY {memories[0].uid[:8]}, {memories[1].uid[:8]}]\n"
    )
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        memories[0].content,
        memories[1].content,
    ]


def test_mem_fit_without_operands_uses_current_context(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, memories = _context(
        store,
        "fit/current",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(app, ["fit", "--plain"])

    assert result.exit_code == 0, result.output
    assert result.output == f"FIT · YES · [TARGETS: CONTEXT {current.name}]\n"
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        memory.content for memory in memories
    ]
    assert [item["role"] for item in question["propositions"]] == [
        "MEMORY",
        "MEMORY",
    ]


def test_mem_fit_without_operands_rejects_one_memory_before_provider(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, _memories = _context(store, "fit/current", "Only one stored claim.")
    store.set_current(current.name)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    monkeypatch.setattr(fit_command, "connect_semantic_provider", provider_factory)

    result = CliRunner().invoke(app, ["fit", "--plain"])

    assert result.exit_code == 1
    assert "at least two propositions" in result.output
    assert calls == 0


def test_mem_fit_auto_resolves_memory_context_and_literal_in_operand_order(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, current_memories = _context(
        store,
        "fit/current",
        "The lobby closes at five.",
    )
    policies, policy_memories = _context(
        store,
        "fit/policies",
        "The side entrance remains open.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        [
            "fit",
            current_memories[0].uid[:8],
            policies.name,
            "Visitors receive an entrance notice.",
            "--plain",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"FIT · YES · [TARGETS: CONTEXT {policies.name}, "
        f"MEMORY {current_memories[0].uid[:8]}, PROPOSITION p1]\n"
    )
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        current_memories[0].content,
        policy_memories[0].content,
        "Visitors receive an entrance notice.",
    ]
    assert [item["role"] for item in question["propositions"]] == [
        "MEMORY",
        "MEMORY",
        "PROPOSITION",
    ]


def test_mem_fit_text_prefix_forces_literal_when_context_name_collides(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, memories = _context(
        store,
        "policies",
        "The side entrance remains open.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        ["fit", "text:policies", memories[0].uid[:7], "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"FIT · YES · [TARGETS: MEMORY {memories[0].uid[:8]}, PROPOSITION p1]\n"
    )
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        "policies",
        memories[0].content,
    ]
    assert [item["role"] for item in question["propositions"]] == [
        "PROPOSITION",
        "MEMORY",
    ]


def test_mem_fit_auto_qualified_memory_uses_relative_context_locator(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, current_memories = _context(
        store,
        "fit/current",
        "The lobby closes at five.",
    )
    sibling, sibling_memories = _context(
        store,
        "fit/sibling",
        "The side entrance remains open.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        [
            "fit",
            current_memories[0].uid[:8],
            f"../sibling:{sibling_memories[0].uid[:8]}",
            "--plain",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"FIT · YES · [TARGETS: MEMORY {current_memories[0].uid[:8]}, "
        f"{sibling_memories[0].uid[:8]}]\n"
    )
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        current_memories[0].content,
        sibling_memories[0].content,
    ]


def test_mem_fit_auto_uid_shape_fails_as_memory_instead_of_becoming_text(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, _memories = _context(store, "fit/current", "One stored claim.")
    store.set_current(current.name)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    monkeypatch.setattr(fit_command, "connect_semantic_provider", provider_factory)
    result = CliRunner().invoke(
        app,
        ["fit", "deadbeef", "Another proposition.", "--plain"],
    )

    assert result.exit_code == 1
    assert "No direct Fit Memory" in result.output
    assert calls == 0


def test_mem_fit_explicit_context_preserves_uid_shaped_legacy_name(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    legacy = Context(uid=str(uuid.uuid4()), name="deadbeef")
    memories = (
        ops.add(legacy, "The lobby closes at five."),
        ops.add(legacy, "The side entrance remains open."),
    )
    _seed_legacy_context(store, legacy)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        ["fit", "--context", legacy.name, "--plain"],
    )

    assert result.exit_code == 0, result.output
    assert result.output == "FIT · YES · [TARGETS: CONTEXT deadbeef]\n"
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        memory.content for memory in memories
    ]


def test_mem_fit_accepts_multiple_contexts_and_relative_memory_qualifier(
    isolated_store,
    monkeypatch,
):
    store = MemoryStore()
    current, _ = _context(store, "fit/current", "The lobby closes at five.")
    sibling, sibling_memories = _context(
        store,
        "fit/sibling",
        "The side entrance remains open.",
    )
    third, third_memories = _context(
        store,
        "fit/third",
        "Staff may use the side entrance.",
    )
    fourth, fourth_memories = _context(
        store,
        "fit/fourth",
        "Visitors receive a side-entrance notice.",
    )
    store.set_current(current.name)
    provider = _FitProvider()
    monkeypatch.setattr(fit_command, "connect_semantic_provider", lambda: provider)

    result = CliRunner().invoke(
        app,
        [
            "fit",
            "--memory",
            f"../sibling:{sibling_memories[0].uid[:8]}",
            "--context",
            third.name,
            "--context",
            fourth.name,
            "--plain",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output == (
        f"FIT · YES · [TARGETS: CONTEXT {third.name}, {fourth.name}, "
        f"MEMORY {sibling_memories[0].uid[:8]}]\n"
    )
    question = provider.payload["questions"][0]
    assert [item["content"] for item in question["propositions"]] == [
        sibling_memories[0].content,
        third_memories[0].content,
        fourth_memories[0].content,
    ]


def test_mem_fit_help_exposes_repeatable_stored_sources() -> None:
    result = CliRunner().invoke(app, ["fit", "--help"])

    assert result.exit_code == 0
    assert "--memory" in result.output
    assert "[CONTEXT:]UID_OR_PREFIX" in result.output
    assert "--context" in result.output
    assert "Repeatable readable Context" in result.output
    assert "Auto operand" in result.output
    assert "text:VALUE" in result.output
    assert "current Context's direct Memories" in result.output


def test_stored_fit_rejects_empty_context_before_provider(isolated_store):
    store = MemoryStore()
    context, _memories = _context(store, "fit/source")
    store.set_current(context.name)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    with pytest.raises(FitSourceError, match="no direct ordinary Memories"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                context_locators=(context.name,),
                propositions=(),
            ),
            store=store,
            provider_factory=provider_factory,
        )
    assert calls == 0


def test_stored_fit_preserves_overlapping_sources_as_operator_operands(
    isolated_store,
):
    store = MemoryStore()
    context, memories = _context(store, "fit/source", "One stored claim.")
    store.set_current(context.name)
    provider = _FitProvider()

    result = run_stored_source_fit(
        FitStoredSourcesRequest(
            propositions=(),
            memory_sources=(FitMemorySourceRequest(memories[0].uid[:8]),),
            context_locators=(context.name,),
        ),
        store=store,
        provider_factory=lambda: provider,
    )

    assert result.analysis.assessment.verdict == "YES"
    assert [item.content for item in result.analysis.question.propositions] == [
        "One stored claim.",
        "One stored claim.",
    ]
    assert [item.kind for item in result.input_origins] == ["MEMORY", "CONTEXT"]


def test_stored_fit_rejects_selected_memory_change_after_provider(
    isolated_store,
):
    store = MemoryStore()
    context, memories = _context(
        store,
        "fit/source",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )
    store.set_current(context.name)

    def change_selected() -> None:
        current = store.load_direct(context.name)
        current.replace(Memory(memories[0].uid, "The lobby closes at six."))
        store.save(current)

    with pytest.raises(FitSourceError, match="Source Memory.*changed"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                propositions=(),
                memory_sources=(
                    FitMemorySourceRequest(memories[0].uid[:8]),
                    FitMemorySourceRequest(memories[1].uid[:8]),
                ),
            ),
            store=store,
            provider_factory=lambda: _FitProvider(change_selected),
        )


def test_background_does_not_replace_second_effective_stored_proposition(
    isolated_store,
):
    store = MemoryStore()
    context, memories = _context(store, "fit/source", "One stored claim.")
    store.set_current(context.name)
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    with pytest.raises(ValueError, match="at least two propositions"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                propositions=(),
                background=(FitProposition("k1", "Background only."),),
                memory_sources=(FitMemorySourceRequest(memories[0].uid[:8]),),
            ),
            store=store,
            provider_factory=provider_factory,
        )
    assert calls == 0


def test_memory_only_fit_ignores_unselected_neighbor_change(isolated_store):
    store = MemoryStore()
    context, memories = _context(
        store,
        "fit/source",
        "The lobby closes at five.",
        "The side entrance remains open.",
        "An unrelated neighboring claim.",
    )
    store.set_current(context.name)

    def change_neighbor() -> None:
        current = store.load_direct(context.name)
        current.replace(Memory(memories[2].uid, "A changed neighboring claim."))
        store.save(current)

    result = run_stored_source_fit(
        FitStoredSourcesRequest(
            propositions=(),
            memory_sources=(
                FitMemorySourceRequest(memories[0].uid[:8]),
                FitMemorySourceRequest(memories[1].uid[:8]),
            ),
        ),
        store=store,
        provider_factory=lambda: _FitProvider(change_neighbor),
    )

    assert result.analysis.assessment.verdict == "YES"


def test_context_fit_rejects_any_direct_memory_change(isolated_store):
    store = MemoryStore()
    context, memories = _context(
        store,
        "fit/source",
        "The lobby closes at five.",
        "The side entrance remains open.",
    )

    def change_context() -> None:
        current = store.load_direct(context.name)
        current.replace(Memory(memories[1].uid, "The side entrance also closes."))
        store.save(current)

    with pytest.raises(FitSourceError, match="Source Context.*changed"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                propositions=(),
                context_locators=(context.name,),
            ),
            store=store,
            provider_factory=lambda: _FitProvider(change_context),
        )


def test_granted_fit_requires_derive_before_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _source, _memories, _grant = _granted_context(
        tmp_path,
        monkeypatch,
        ("READ",),
    )
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    with pytest.raises(ProfileError, match="DERIVE"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                propositions=(),
                context_locators=("shared/fit-source",),
            ),
            store=store,
            provider_factory=provider_factory,
        )
    assert calls == 0


def test_granted_fit_requires_combine_with_literal_and_then_succeeds(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _source, memories, grant = _granted_context(
        tmp_path,
        monkeypatch,
        ("READ", "DERIVE"),
    )
    request = FitStoredSourcesRequest(
        propositions=(FitProposition("p1", "Visitors use the lobby."),),
        memory_sources=(
            FitMemorySourceRequest(
                memories[0].uid[:8],
                context_locator="shared/fit-source",
            ),
        ),
    )
    calls = 0

    def provider_factory():
        nonlocal calls
        calls += 1
        return _FitProvider()

    with pytest.raises(ProfileError, match="COMBINE"):
        run_stored_source_fit(
            request,
            store=store,
            provider_factory=provider_factory,
        )
    assert calls == 0

    update_authority_grant(
        grant.uid,
        permissions=("READ", "DERIVE", "COMBINE"),
    )
    result = run_stored_source_fit(
        FitStoredSourcesRequest(
            propositions=(FitProposition("p1", "Visitors use the lobby."),),
            memory_sources=(
                FitMemorySourceRequest(
                    memories[0].uid[:8],
                    context_locator="shared/fit-source",
                ),
            ),
        ),
        store=store,
        provider_factory=lambda: _FitProvider(),
    )
    assert result.analysis.assessment.verdict == "YES"


def test_granted_fit_revalidates_exact_grant_after_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    store, _source, _memories, grant = _granted_context(
        tmp_path,
        monkeypatch,
        ("READ", "DERIVE"),
    )

    def revise_grant() -> None:
        update_authority_grant(
            grant.uid,
            permissions=("READ", "DERIVE"),
        )

    with pytest.raises(ProfileError, match="grant changed"):
        run_stored_source_fit(
            FitStoredSourcesRequest(
                propositions=(),
                context_locators=("shared/fit-source",),
            ),
            store=store,
            provider_factory=lambda: _FitProvider(revise_grant),
        )
