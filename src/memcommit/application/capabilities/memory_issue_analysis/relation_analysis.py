"""Whole-frame relation analysis for Memory redundancy and conflict."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping

from memcommit.application.capabilities.memory_issue_analysis import provider_contract
from memcommit.application.capabilities.memory_issue_analysis.model import (
    ConflictFinding,
    ConflictReport,
    DuplicateFinding,
    DuplicateReport,
    FindingsError,
    FindingsProvider,
)
from memcommit.application.capabilities.reviewing.direct_item_duplicates import (
    ExactDuplicateGroup,
    find_exact_duplicate_groups,
)
from memcommit.models.context import Context

_CONFLICT_LABELS = {"YES", "MAY"}


def _is_horizontal_space(character: str) -> bool:
    """Keep vertical separators distinct while recognizing Unicode spaces."""
    return character == "\t" or unicodedata.category(character) == "Zs"


def _trim_horizontal(value: str) -> str:
    start = 0
    end = len(value)
    while start < end and _is_horizontal_space(value[start]):
        start += 1
    while end > start and _is_horizontal_space(value[end - 1]):
        end -= 1
    return value[start:end]


def _collapse_horizontal(value: str) -> str:
    result: list[str] = []
    in_space = False
    for character in value:
        if _is_horizontal_space(character):
            if not in_space:
                result.append(" ")
            in_space = True
        else:
            result.append(character)
            in_space = False
    return "".join(result)


def _surface_key(content: str) -> str:
    """Return a conservative comparison key without rewriting stored text."""
    normalized = unicodedata.normalize(
        "NFC",
        content.replace("\r\n", "\n").replace("\r", "\n"),
    )
    # Outer trimming intentionally removes only line breaks and horizontal
    # spaces. Other vertical separators remain semantic structure.
    start = 0
    end = len(normalized)
    while start < end and (
        normalized[start] == "\n" or _is_horizontal_space(normalized[start])
    ):
        start += 1
    while end > start and (
        normalized[end - 1] == "\n" or _is_horizontal_space(normalized[end - 1])
    ):
        end -= 1
    normalized = normalized[start:end]
    return "\n".join(
        _trim_horizontal(_collapse_horizontal(line)) for line in normalized.split("\n")
    )


def _mechanical_duplicate_forest(
    candidates: list[provider_contract.MemoryCandidate],
    exact_groups: tuple[ExactDuplicateGroup, ...],
) -> tuple[list[DuplicateFinding], list[provider_contract.MemoryCandidate]]:
    """Find exact/surface components without constructing their pair cliques."""
    findings: list[DuplicateFinding] = []
    candidate_by_uid = {candidate.memory.uid: candidate for candidate in candidates}
    exact_survivors = {
        uid: group.survivor_uid for group in exact_groups for uid in group.absorbed_uids
    }
    surface_representatives: dict[str, provider_contract.MemoryCandidate] = {}
    semantic_representatives: list[provider_contract.MemoryCandidate] = []
    for candidate in candidates:
        content = candidate.memory.content
        exact = candidate_by_uid.get(exact_survivors.get(candidate.memory.uid))
        if exact is not None:
            findings.append(
                DuplicateFinding(
                    left=exact.memory,
                    right=candidate.memory,
                    relation="EXACT",
                    reason="Stored content is identical.",
                )
            )
            continue
        surface_key = _surface_key(content)
        surface = surface_representatives.get(surface_key)
        if surface is not None:
            findings.append(
                DuplicateFinding(
                    left=surface.memory,
                    right=candidate.memory,
                    relation="SURFACE_EQUIVALENT",
                    reason="Content differs only under conservative Unicode, line-ending, outer-space, or horizontal-space normalization.",
                )
            )
            continue
        surface_representatives[surface_key] = candidate
        semantic_representatives.append(candidate)
    return (findings, semantic_representatives)


def _ordered_duplicate_findings(
    candidates: list[provider_contract.MemoryCandidate],
    findings: list[DuplicateFinding],
) -> tuple[DuplicateFinding, ...]:
    """Restore Context order after provider groups are locally canonicalized."""
    order_by_uid = {
        candidate.memory.uid: index for index, candidate in enumerate(candidates)
    }

    def finding_key(finding: DuplicateFinding) -> tuple[int, int]:
        return (
            order_by_uid[finding.left.uid],
            order_by_uid[finding.right.uid],
        )

    return tuple(sorted(findings, key=finding_key))


def analyze_memory_redundancies(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
    exact_groups: tuple[ExactDuplicateGroup, ...] | None = None,
) -> DuplicateReport:
    """Discover complete DUN evidence: exact DUP plus semantic redundancy."""
    candidates = provider_contract.collect_direct_memories(
        context, context_name_by_uid=context_name_by_uid
    )
    if exact_groups is None:
        exact_groups = find_exact_duplicate_groups(context)
    mechanical, semantic_candidates = _mechanical_duplicate_forest(
        candidates, exact_groups
    )
    findings = list(mechanical)
    if len(semantic_candidates) >= 2:
        prompt_policy, calibration_cases = provider_contract._prompt_calibration_cases(
            "duplicates.json"
        )
        candidate_by_id = {
            candidate.candidate_id: candidate for candidate in semantic_candidates
        }
        item_schema: dict[str, object] = {
            "type": "object",
            "properties": {
                "candidate_ids": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": len(semantic_candidates),
                    "items": {"type": "string", "enum": list(candidate_by_id)},
                },
                "relation": {"type": "string", "enum": ["SEMANTIC_EQUIVALENT"]},
                "reason": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": provider_contract.QUALITY_REASON_CHAR_LIMIT,
                },
            },
            "required": ["candidate_ids", "relation", "reason"],
            "additionalProperties": False,
        }
        records = provider_contract._call_once(
            provider_factory=provider_factory,
            operation="find_duplicates",
            instructions="You discover semantically duplicate atomic Memories inside one selected Context frame. The frame may combine several readable Contexts, and each candidate carries its original context_name. The supplied Memories are one representative from each exact/surface-equivalent component; do not construct or request an all-pairs comparison table. Treat each candidate's complete stored content as one indivisible judgment unit: do not split a Memory or extract matching substrings or propositions. If only a proper part would be redundant, omit the group; Atomize must first make that part a separately reviewable Memory. Return disjoint groups of two or more candidate IDs only when every member is mutually substitutable without information loss under the same subject, predicate, object, place, audience, time, modality, condition, access method, and exception. Do not return mere entailment, overlap, related information, uncertain scope, or distinct claims. A candidate may occur in at most one returned group. Omit candidates for which you discover no semantic-equivalence group. Absence is not proof that no duplicate exists.",
            payload={
                "operation": "find_duplicates",
                **(
                    {"prompt_policy": prompt_policy}
                    if prompt_policy is not None
                    else {}
                ),
                "context": {
                    "name": context.name,
                    "direct_memory_count": len(candidates),
                },
                "memories": provider_contract._memory_payload(semantic_candidates),
                "calibration_cases": calibration_cases,
            },
            schema=provider_contract._findings_schema(
                item_schema, max_items=len(semantic_candidates) // 2
            ),
        )
        used_candidate_ids: set[str] = set()
        candidate_order = {
            candidate.candidate_id: index
            for index, candidate in enumerate(semantic_candidates)
        }
        semantic_groups: list[tuple[list[provider_contract.MemoryCandidate], str]] = []
        for value in records:
            record = provider_contract._exact_dict(
                value,
                {"candidate_ids", "relation", "reason"},
                operation="find_duplicates",
            )
            candidate_ids = record["candidate_ids"]
            if (
                not isinstance(candidate_ids, list)
                or len(candidate_ids) < 2
                or len(candidate_ids) > len(semantic_candidates)
                or (
                    len(
                        {
                            candidate_id
                            for candidate_id in candidate_ids
                            if isinstance(candidate_id, str)
                        }
                    )
                    != len(candidate_ids)
                )
                or any(
                    not isinstance(candidate_id, str)
                    or candidate_id not in candidate_by_id
                    for candidate_id in candidate_ids
                )
                or any(
                    candidate_id in used_candidate_ids for candidate_id in candidate_ids
                )
                or (record["relation"] != "SEMANTIC_EQUIVALENT")
            ):
                raise FindingsError(
                    "Codex find_duplicates returned an unknown, repeated, overlapping, or invalid duplicate group."
                )
            ordered_ids = sorted(candidate_ids, key=candidate_order.__getitem__)
            used_candidate_ids.update(ordered_ids)
            reason = provider_contract._short_string(
                record["reason"],
                operation="find_duplicates",
                label="reason",
                limit=provider_contract.QUALITY_REASON_CHAR_LIMIT,
            )
            semantic_groups.append(
                (
                    [candidate_by_id[candidate_id] for candidate_id in ordered_ids],
                    reason,
                )
            )
        semantic_groups.sort(
            key=lambda group: candidate_order[group[0][0].candidate_id]
        )
        for group, reason in semantic_groups:
            representative = group[0]
            for member in group[1:]:
                findings.append(
                    DuplicateFinding(
                        left=representative.memory,
                        right=member.memory,
                        relation="SEMANTIC_EQUIVALENT",
                        reason=reason,
                    )
                )
    return DuplicateReport(
        memory_count=len(candidates),
        findings=_ordered_duplicate_findings(candidates, findings),
    )


def analyze_memory_conflicts(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
) -> ConflictReport:
    """Find conflicting unordered Memory pairs in one provider call."""
    candidates = provider_contract.collect_direct_memories(
        context,
        context_name_by_uid=context_name_by_uid,
    )
    pairs = provider_contract.enumerate_pairs(candidates)
    if not pairs:
        return ConflictReport(
            memory_count=len(candidates),
            pair_count=0,
            findings=(),
        )
    by_id = {pair.pair_id: pair for pair in pairs}
    item_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "pair_id": {
                "type": "string",
                "enum": list(by_id),
            },
            "conflict": {
                "type": "string",
                "enum": sorted(_CONFLICT_LABELS),
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": provider_contract.QUALITY_REASON_CHAR_LIMIT,
                "description": "One English sentence, at most 10 whitespace-delimited words.",
                "pattern": r"^\S+(?:[ \t]+\S+){0,9}$",
            },
        },
        "required": [
            "pair_id",
            "conflict",
            "reason",
        ],
        "additionalProperties": False,
    }
    prompt_policy, calibration_cases = provider_contract._prompt_calibration_cases(
        "conflict.json"
    )
    records = provider_contract._call_once(
        provider_factory=provider_factory,
        operation="find_conflicts",
        instructions=(
            "You find semantically conflicting pairs of atomic Memories inside "
            "one selected Context frame. The frame may combine several readable "
            "Contexts, and each candidate carries its original context_name. "
            "Inspect every supplied unordered pair, including cross-Context "
            "pairs, under ordinary common-sense readings of the complete frame. "
            "Return YES when the pair conflicts across its ordinary readings. "
            "Return MAY only when multiple ordinary readings or an unstated "
            "scope distinction make the pair conflicting under some readings "
            "and jointly explainable under others. MAY is semantic "
            "indeterminacy, never low model confidence. Omit NO pairs that are "
            "jointly explainable. Do not invent exotic assumptions to force "
            "compatibility. Write reason as one English sentence of at most "
            "10 whitespace-delimited words. Pinpoint the disagreement for YES "
            "or the unresolved meaning or scope for MAY. Do not enumerate "
            "interpretations, repeat the Memories, ask a question, or propose "
            "a solution. Keep the distinction between definite conflict and "
            "unresolved meaning explicit."
        ),
        payload={
            "operation": "find_conflicts",
            **({"prompt_policy": prompt_policy} if prompt_policy is not None else {}),
            "context": {"name": context.name},
            "memories": provider_contract._memory_payload(candidates),
            "pairs": provider_contract._pair_payload(pairs),
            "calibration_cases": calibration_cases,
        },
        schema=provider_contract._findings_schema(item_schema, max_items=len(pairs)),
    )
    findings: dict[str, ConflictFinding] = {}
    for value in records:
        record = provider_contract._exact_dict(
            value,
            {
                "pair_id",
                "conflict",
                "reason",
            },
            operation="find_conflicts",
        )
        pair_id = record["pair_id"]
        conflict = record["conflict"]
        if (
            not isinstance(pair_id, str)
            or pair_id not in by_id
            or pair_id in findings
            or conflict not in _CONFLICT_LABELS
        ):
            raise FindingsError(
                "Codex find_conflicts returned an unknown, duplicate, or "
                "invalid finding."
            )
        reason = provider_contract._short_string(
            record["reason"],
            operation="find_conflicts",
            label="reason",
            limit=provider_contract.QUALITY_REASON_CHAR_LIMIT,
        )
        if len(reason.split()) > provider_contract.CONFLICT_REASON_WORD_LIMIT or any(
            separator in reason for separator in ("\n", "\r")
        ):
            raise FindingsError(
                "Conflict reason must be one line with at most 10 words."
            )
        pair = by_id[pair_id]
        findings[pair_id] = ConflictFinding(
            left=pair.left.memory,
            right=pair.right.memory,
            conflict=conflict,  # type: ignore[arg-type]
            reason=reason,
        )
    return ConflictReport(
        memory_count=len(candidates),
        pair_count=len(pairs),
        findings=tuple(
            findings[pair.pair_id] for pair in pairs if pair.pair_id in findings
        ),
    )


__all__ = ["analyze_memory_conflicts", "analyze_memory_redundancies"]
