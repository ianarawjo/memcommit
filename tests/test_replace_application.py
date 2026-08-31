"""Pure frozen-plan tests for deterministic Replace."""

from __future__ import annotations

import pytest

from memcommit.application.operations.direct_changes.replace.application import (
    FrozenReplaceContext,
    FrozenReplaceSource,
    ReplaceApplyResult,
    ReplaceError,
    ReplaceRequest,
    ReplaceSourceMemory,
    apply_replace,
    plan_replace,
)


class _Port:
    def __init__(self, contexts):
        self.contexts = contexts
        self.token = object()
        self.applied = []

    def freeze(self, _request):
        return FrozenReplaceSource(self.contexts, token=self.token)

    def apply(self, plan):
        self.applied.append(plan)
        return ReplaceApplyResult(
            plan_digest=plan.plan_digest,
            applied=False,
            scanned_context_count=plan.scanned_context_count,
            scanned_memory_count=plan.scanned_memory_count,
            matched_memory_count=plan.matched_memory_count,
            changed_memory_count=plan.changed_memory_count,
            occurrence_count=plan.occurrence_count,
            checkpoints=(),
        )


def _context(*contents: str):
    return FrozenReplaceContext(
        name="alpha",
        uid="context-1",
        digest="a" * 64,
        memories=tuple(
            ReplaceSourceMemory(uid=f"memory-{index}", content=content)
            for index, content in enumerate(contents, start=1)
        ),
    )


def test_replace_plan_is_complete_and_digest_is_reproducible() -> None:
    request = ReplaceRequest(
        pattern="needle",
        replacement="thread",
        target_names=("alpha",),
        ignore_case=True,
    )
    first = plan_replace(request, port=_Port((_context("Needle, needle.", "other"),)))
    second = plan_replace(request, port=_Port((_context("Needle, needle.", "other"),)))

    assert first.plan_digest == second.plan_digest
    assert first.scanned_context_count == 1
    assert first.scanned_memory_count == 2
    assert first.matched_memory_count == 1
    assert first.changed_memory_count == 1
    assert first.occurrence_count == 2
    change = first.contexts[0].matches[0]
    assert change.before_content == "Needle, needle."
    assert change.after_content == "thread, thread."
    assert [(span.start, span.end) for span in change.spans] == [(0, 6), (8, 14)]


def test_regex_changes_use_literal_replacement_text_not_backreferences() -> None:
    plan = plan_replace(
        ReplaceRequest(
            pattern=r"(alpha)",
            replacement=r"\1-safe",
            target_names=("alpha",),
            mode="REGEX",
        ),
        port=_Port((_context("alpha"),)),
    )

    assert plan.contexts[0].matches[0].after_content == r"\1-safe"


def test_identical_replacement_retains_matches_but_has_no_effect() -> None:
    port = _Port((_context("alpha alpha"),))
    plan = plan_replace(
        ReplaceRequest("alpha", "alpha", ("alpha",)),
        port=port,
    )
    result = apply_replace(plan, port=port)

    assert plan.occurrence_count == 2
    assert plan.matched_memory_count == 1
    assert plan.changed_memory_count == 0
    assert result.applied is False
    assert port.applied == [plan]


def test_replace_rejects_zero_width_regex_before_freezing_source() -> None:
    class _ForbiddenPort(_Port):
        def freeze(self, _request):
            raise AssertionError("invalid regex must fail before source access")

    with pytest.raises(ValueError, match="consume at least one character"):
        plan_replace(
            ReplaceRequest("^|", "x", ("alpha",), mode="REGEX"),
            port=_ForbiddenPort((_context("alpha"),)),
        )


def test_apply_rejects_plan_tampering_before_runtime() -> None:
    port = _Port((_context("alpha"),))
    plan = plan_replace(ReplaceRequest("a", "b", ("alpha",)), port=port)
    object.__setattr__(plan, "plan_digest", "0" * 64)

    with pytest.raises(ReplaceError, match="does not match its digest"):
        apply_replace(plan, port=port)
    assert port.applied == []
