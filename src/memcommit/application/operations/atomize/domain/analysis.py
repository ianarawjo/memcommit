"""Candidate selection and non-mutating Atomize analysis orchestration."""

from __future__ import annotations

import re
from typing import Callable

from memcommit.application.capabilities.semantic.prompt_policy import (
    SemanticPromptPolicy,
    resolve_semantic_prompt_policy,
)
from memcommit.core.context import Context, Memory
from memcommit.application.capabilities.semantic.memory_scope import (
    MemoryScopeError,
    resolve_memory_scope,
)

from .model import (
    ATOMIZE_DECLARED_FRAME_CHAR_LIMIT,
    ATOMIZE_SIZE_REVIEW_CHARS,
    ATOMIZE_SIZE_REVIEW_SEGMENTS,
    AtomizeCandidate,
    AtomizeImpactError,
    AtomizeImpactReport,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeProvider,
)
from .provider_contract.prompt import _payload, _prompt
from .provider_contract.response.entrypoint import parse_response
from .provider_contract.response_schema import _output_schema


_SEGMENT_BOUNDARY = re.compile(r"[.!?。？！]+(?=\s|$)")


def sentence_like_segment_count(content: str) -> int:
    """Count deterministic surface segments for the review-only size lint."""
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    count = 0
    for line in normalized.split("\n"):
        if not line.strip():
            continue
        count += sum(
            bool(segment.strip())
            for segment in _SEGMENT_BOUNDARY.split(line)
        )
    return count


def atomize_lint(content: str) -> tuple[str, ...]:
    """Return local review signals; lint never determines atomicity."""
    if (
        len(content) > ATOMIZE_SIZE_REVIEW_CHARS
        or sentence_like_segment_count(content)
        > ATOMIZE_SIZE_REVIEW_SEGMENTS
    ):
        return ("SIZE_REVIEW",)
    return ()


def collect_atomize_candidates(ctx: Context) -> list[AtomizeCandidate]:
    """Collect direct Memories in Context order without following references."""
    candidates: list[AtomizeCandidate] = []
    for item in ctx.iter_items():
        if not isinstance(item, Memory):
            continue
        candidates.append(
            AtomizeCandidate(
                candidate_id=f"m{len(candidates) + 1:06d}",
                # The preview is direct-Memory-only.  A non-Memory pointer may
                # be unresolved by load_direct() and restored by a mutating
                # load, so binding to all-item slots would make an unchanged
                # Memory appear stale merely because a pointer became visible.
                position=len(candidates),
                memory=item,
                lint=atomize_lint(item.content),
            )
        )
    return candidates


def select_atomize_candidates(
    ctx: Context,
    memory_selector: str | None,
) -> tuple[list[AtomizeCandidate], list[AtomizeCandidate]]:
    """Return actionable candidates and separately frozen context evidence."""

    candidates = collect_atomize_candidates(ctx)
    try:
        scope = resolve_memory_scope(
            candidates,
            memory_selector,
            label="direct Memory",
        )
    except MemoryScopeError as error:
        raise AtomizeImpactError(str(error)) from error
    return list(scope.actionable), list(scope.context_only)


def impact_atomize(
    ctx: Context,
    provider_factory: Callable[[], AtomizeProvider],
    *,
    declared_frames: dict[str, str] | None = None,
    memory_selector: str | None = None,
    _memory_uids: tuple[str, ...] | None = None,
    _normal_form_validation: bool = False,
    _prompt_policy: SemanticPromptPolicy | None = None,
    _input_char_limit: int | None = None,
) -> AtomizeImpactReport:
    """Return one non-mutating, provisional atomization impact report."""
    declared_frames = declared_frames or {}
    prompt_policy = _prompt_policy or resolve_semantic_prompt_policy()
    if memory_selector is not None and _memory_uids is not None:
        raise AtomizeImpactError("Atomize received conflicting Memory scopes.")
    if _memory_uids is None:
        candidates, context_only = select_atomize_candidates(
            ctx,
            memory_selector,
        )
    else:
        requested = set(_memory_uids)
        all_candidates = collect_atomize_candidates(ctx)
        if (
            len(requested) != len(_memory_uids)
            or requested
            - {candidate.memory.uid for candidate in all_candidates}
        ):
            raise AtomizeImpactError(
                "Atomize validation scope contains an unknown direct Memory."
            )
        # The internal multi-Memory scope is used only to verify the complete
        # affected output of one unpublished composite command. Neighboring
        # direct Memories remain context evidence, as in ordinary focus mode.
        candidates = [
            candidate
            for candidate in all_candidates
            if candidate.memory.uid in requested
        ]
        context_only = [
            candidate
            for candidate in all_candidates
            if candidate.memory.uid not in requested
        ]
    candidate_uids = {candidate.memory.uid for candidate in candidates}
    if any(
        not isinstance(uid, str)
        or uid not in candidate_uids
        or not isinstance(text, str)
        or not text.strip()
        or len(text) > ATOMIZE_DECLARED_FRAME_CHAR_LIMIT
        for uid, text in declared_frames.items()
    ):
        raise AtomizeImpactError("Invalid atomize declared frame.")
    if not candidates:
        return AtomizeImpactReport(
            context_uid=ctx.uid,
            context_name=ctx.name,
            memory_count=0,
            projected_memory_count=0,
            items=(),
            overview=AtomizeOverview(
                understood=AtomizeOverviewSection(
                    text="The selected Context has no direct Memories."
                ),
                changed=AtomizeOverviewSection(
                    text="No atomization change is proposed."
                ),
                unresolved=AtomizeOverviewSection(
                    text="No unresolved local expression was found."
                ),
            ),
            quality_issues=(),
            prompt_policy_id=prompt_policy.policy_id,
        )

    payload = _payload(
        ctx,
        candidates,
        declared_frames,
        context_only,
        prompt_policy=prompt_policy,
    )
    if _normal_form_validation:
        # This is provider-visible semantic scope, not a trusted instruction:
        # the same strict Atomize decoder remains authoritative.
        payload["phase"] = "normal_form_validation"
    prompt = _prompt(
        payload,
        **(
            {"input_char_limit": _input_char_limit}
            if _input_char_limit is not None
            else {}
        ),
    )
    provider = provider_factory()
    raw = provider.complete(
        prompt,
        operation="impact_atomize",
        output_schema=_output_schema(candidates),
    )
    items, overview, quality_issues = parse_response(
        raw,
        candidates,
        declared_frames,
    )
    projected_memory_count = len(items)
    for item in items:
        if item.classification == "COMPOSITE":
            projected_memory_count += len(item.children) - 1

    return AtomizeImpactReport(
        context_uid=ctx.uid,
        context_name=ctx.name,
        memory_count=len(items),
        projected_memory_count=projected_memory_count,
        items=items,
        overview=overview,
        quality_issues=quality_issues,
        prompt_policy_id=prompt_policy.policy_id,
    )
