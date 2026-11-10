"""Context-aware reading analysis for Memory ambiguity."""

from __future__ import annotations

from collections.abc import Callable, Mapping

from memcommit.application.capabilities.memory_issue_analysis import provider_contract
from memcommit.application.capabilities.memory_issue_analysis.model import (
    AmbiguityFinding,
    AmbiguityReport,
    FindingsError,
    FindingsProvider,
)
from memcommit.models.context import Context

_INTERPRETATIONS = {"SINGLE", "DOMINANT", "COMPETING"}
_CLARIFICATIONS = {"NONE", "HELPFUL", "REQUIRED"}


def analyze_memory_ambiguities(
    context: Context,
    provider_factory: Callable[[], FindingsProvider],
    *,
    context_name_by_uid: Mapping[str, str] | None = None,
) -> AmbiguityReport:
    """Find ambiguous or underspecified direct Memories in one provider call."""
    candidates = provider_contract.collect_direct_memories(
        context,
        context_name_by_uid=context_name_by_uid,
    )
    if not candidates:
        return AmbiguityReport(memory_count=0, findings=())
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    item_schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "candidate_id": {
                "type": "string",
                "enum": list(by_id),
            },
            "interpretation": {
                "type": "string",
                "enum": sorted(_INTERPRETATIONS),
            },
            "clarification": {
                "type": "string",
                "enum": sorted(_CLARIFICATIONS),
            },
            "ordinary_readings": {
                "type": "array",
                "maxItems": provider_contract.QUALITY_READING_LIMIT,
                "items": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": provider_contract.QUALITY_QUESTION_CHAR_LIMIT,
                },
            },
            "reason": {
                "type": "string",
                "minLength": 1,
                "maxLength": provider_contract.QUALITY_REASON_CHAR_LIMIT,
            },
            "question": {
                "type": "string",
                "minLength": 1,
                "maxLength": provider_contract.QUALITY_QUESTION_CHAR_LIMIT,
            },
        },
        "required": [
            "candidate_id",
            "interpretation",
            "clarification",
            "ordinary_readings",
            "reason",
            "question",
        ],
        "additionalProperties": False,
    }
    prompt_policy, calibration_cases = provider_contract._prompt_calibration_cases(
        "ambiguity.json"
    )
    has_examples = bool(calibration_cases)
    ordinary_resolution_example = (
        "For example, 'the main entrance closes at 5' followed by 'after that "
        "time a card is required' resolves the time for this quality scan, and "
        "'if it does not work, call' ordinarily continues a preceding card/NFC "
        "failure sequence. "
        if has_examples
        else ""
    )
    records = provider_contract._call_once(
        provider_factory=provider_factory,
        operation="find_ambiguities",
        instructions=(
            "You find ambiguous or underspecified atomic Memories in one "
            "selected Context frame. The frame may combine several readable "
            "Contexts, and each candidate carries its original context_name. "
            "Interpret each Memory using the complete combined frame and "
            "ordinary common-sense reading; do "
            "not invent remote possible worlds merely to create or remove an "
            "ambiguity. First resolve ordinary antecedents, ellipsis, deixis, "
            "and shared scope against every supplied Memory. A target that is "
            "not self-contained is not thereby ambiguous: when the Context "
            "supplies one usable reading and no operational decision changes, "
            "it is clean SINGLE/NONE and must be omitted. "
            + ordinary_resolution_example
            + "SINGLE/REQUIRED is valid only when the complete "
            "Context still lacks information necessary to perform or reliably "
            "verify an explicit operation, not for optional precision or "
            "wayfinding.\n\n"
            "Reading structure is SINGLE when there is one ordinary "
            "reading, DOMINANT when one reading is ordinary but alternatives "
            "remain live, and COMPETING when multiple ordinary readings lack "
            "a single dominant reading. Clarification need is NONE, HELPFUL, "
            "or REQUIRED according to whether clarification would materially "
            "help or is needed for a reliable operational result. Return every "
            "Memory except the clean SINGLE/NONE combination. Intentional "
            "ambiguity may therefore be COMPETING/NONE. Return exactly one "
            "ordinary reading for SINGLE and at least two for DOMINANT or "
            "COMPETING; list the dominant reading first. Write every ordinary "
            "reading, reason, and question in English even when the source "
            "Memory uses another language. The reason must name the ambiguous "
            "expression or missing information and connect both labels to a "
            "concrete operational consequence. For REQUIRED, state what "
            "cannot be determined reliably; for HELPFUL, state what remains "
            "possible and what clarification would make more precise; for "
            "NONE, state why no operational result depends on resolving the "
            "readings. If the same uncertainty blocks additional decisions, "
            "name them in additional concise sentences rather than generic "
            "topic labels. Supply the smallest useful question for HELPFUL or "
            "REQUIRED; use an empty question for NONE. Never expose candidate "
            "IDs in human-facing readings, reasons, or questions."
        ),
        payload={
            "operation": "find_ambiguities",
            **({"prompt_policy": prompt_policy} if prompt_policy is not None else {}),
            "context": {"name": context.name},
            "memories": provider_contract._memory_payload(candidates),
            "calibration_cases": calibration_cases,
        },
        schema=provider_contract._findings_schema(
            item_schema, max_items=len(candidates)
        ),
    )
    findings: dict[str, AmbiguityFinding] = {}
    for value in records:
        record = provider_contract._exact_dict(
            value,
            {
                "candidate_id",
                "interpretation",
                "clarification",
                "ordinary_readings",
                "reason",
                "question",
            },
            operation="find_ambiguities",
        )
        candidate_id = record["candidate_id"]
        interpretation = record["interpretation"]
        clarification = record["clarification"]
        readings = record["ordinary_readings"]
        if (
            not isinstance(candidate_id, str)
            or candidate_id not in by_id
            or candidate_id in findings
            or interpretation not in _INTERPRETATIONS
            or clarification not in _CLARIFICATIONS
            or not isinstance(readings, list)
            or len(readings) > provider_contract.QUALITY_READING_LIMIT
        ):
            raise FindingsError(
                "Codex find_ambiguities returned an unknown, duplicate, or "
                "invalid finding."
            )
        if interpretation == "SINGLE" and clarification == "NONE":
            raise FindingsError(
                "Codex find_ambiguities returned a clean Memory as a finding."
            )
        ordinary_readings: list[str] = []
        for reading in readings:
            parsed = provider_contract._short_string(
                reading,
                operation="find_ambiguities",
                label="ordinary reading",
                limit=provider_contract.QUALITY_QUESTION_CHAR_LIMIT,
            )
            if parsed in ordinary_readings:
                raise FindingsError(
                    "Codex find_ambiguities returned duplicate readings."
                )
            ordinary_readings.append(parsed)
        if interpretation == "SINGLE" and len(ordinary_readings) != 1:
            raise FindingsError(
                "Codex find_ambiguities returned an invalid SINGLE reading."
            )
        if interpretation in {"DOMINANT", "COMPETING"} and len(ordinary_readings) < 2:
            raise FindingsError(
                "Codex find_ambiguities omitted ordinary alternative readings."
            )
        question = provider_contract._short_string(
            record["question"],
            operation="find_ambiguities",
            label="question",
            limit=provider_contract.QUALITY_QUESTION_CHAR_LIMIT,
            empty=True,
        )
        if clarification == "NONE" and question:
            raise FindingsError("Codex find_ambiguities returned a question for NONE.")
        if clarification != "NONE" and not question.strip():
            raise FindingsError(
                "Codex find_ambiguities omitted a clarification question."
            )
        candidate = by_id[candidate_id]
        findings[candidate_id] = AmbiguityFinding(
            memory=candidate.memory,
            interpretation=interpretation,  # type: ignore[arg-type]
            clarification=clarification,  # type: ignore[arg-type]
            ordinary_readings=tuple(ordinary_readings),
            reason=provider_contract._short_string(
                record["reason"],
                operation="find_ambiguities",
                label="reason",
                limit=provider_contract.QUALITY_REASON_CHAR_LIMIT,
            ),
            question=question,
        )
    return AmbiguityReport(
        memory_count=len(candidates),
        findings=tuple(
            findings[candidate.candidate_id]
            for candidate in candidates
            if candidate.candidate_id in findings
        ),
    )


__all__ = ["analyze_memory_ambiguities"]
