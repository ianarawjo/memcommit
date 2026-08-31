"""Public compatibility facade for the Atomize domain package.

Implementation lives in five responsibility-focused modules. Existing imports
from ``memcommit.application.operations.semantic_updates.derive.atomize.domain`` remain stable.
"""

# ruff: noqa: F401

from typing import Callable

from memcommit.application.capabilities.semantic.prompt_policy import (
    resolve_semantic_prompt_policy,
)
from memcommit.core.context import Context

from .analysis import (
    _SEGMENT_BOUNDARY,
    impact_atomize as _impact_atomize_impl,
    atomize_lint,
    collect_atomize_candidates,
    select_atomize_candidates,
    sentence_like_segment_count,
)
from .model import (
    ATOMIZE_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_CHILD_CHAR_LIMIT,
    ATOMIZE_CHILD_LIMIT,
    ATOMIZE_CLASSIFICATIONS,
    ATOMIZE_CLARIFICATIONS,
    ATOMIZE_CONFLICTS,
    ATOMIZE_DECLARED_FRAME_CHAR_LIMIT,
    ATOMIZE_FOCUSED_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_INPUT_CHAR_LIMIT,
    ATOMIZE_INTERPRETATIONS,
    ATOMIZE_LEGACY_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_LEGACY_RULESET_VERSION,
    ATOMIZE_OVERVIEW_CHAR_LIMIT,
    ATOMIZE_PROVIDER_CONTRACT_VERSION,
    ATOMIZE_QUALITY_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_QUALITY_KINDS,
    ATOMIZE_QUALITY_READING_LIMIT,
    ATOMIZE_READING_LABEL_CHAR_LIMIT,
    ATOMIZE_READING_LABEL_WORD_LIMIT,
    ATOMIZE_READING_ROLES,
    ATOMIZE_REASON_CHAR_LIMIT,
    ATOMIZE_RESPONSE_CHAR_LIMIT,
    ATOMIZE_REVIEWED_ANALYSIS_SCHEMA_VERSION,
    ATOMIZE_RULESET_VERSION,
    ATOMIZE_RULES,
    ATOMIZE_RULE_CODES,
    ATOMIZE_SCOPE_DIMENSIONS,
    ATOMIZE_SEGMENTER_VERSION,
    ATOMIZE_SIZE_REVIEW_CHARS,
    ATOMIZE_SIZE_REVIEW_SEGMENTS,
    ATOMIZE_SOURCE_SPAN_LIMIT,
    AtomizeCandidate,
    AtomizeChild,
    AtomizeClarification,
    AtomizeClassification,
    AtomizeConflict,
    AtomizeImpactError,
    AtomizeImpactReport,
    AtomizeInterpretation,
    AtomizeItem,
    AtomizeOverview,
    AtomizeOverviewSection,
    AtomizeProvider,
    AtomizeQualityIssue,
    AtomizeQualityKind,
    AtomizeReading,
    AtomizeReadingRole,
    _reading_roles,
)
from .provider_contract import (
    _atomize_execution_policy,
    _exact_dict,
    _load_calibration,
    _output_schema,
    _parse_items,
    _parse_overview,
    _parse_quality_issues,
    _payload,
    _prompt,
    _reject_duplicate_json_keys,
    _short_string,
)
from .session import (
    AtomizeAnalysisItem,
    AtomizeAnalysisSession,
    AtomizeDeclaredFrame,
    AtomizeFrameOrigin,
    _atomize_items_digest,
    _legacy_overview,
    atomize_analysis_matches_context,
    atomize_declared_frame_digest,
    create_atomize_analysis,
)
from .structural_apply import (
    AppliedAtomizeItem,
    AtomizeApplyResult,
    AtomizeNormalFormAudit,
    apply_atomize_analysis,
)


def impact_atomize(
    ctx: Context,
    provider_factory: Callable[[], AtomizeProvider],
    *,
    declared_frames: dict[str, str] | None = None,
    memory_selector: str | None = None,
    _memory_uids: tuple[str, ...] | None = None,
    _normal_form_validation: bool = False,
) -> AtomizeImpactReport:
    """Preserve legacy module-level policy and limit override seams."""

    return _impact_atomize_impl(
        ctx,
        provider_factory,
        declared_frames=declared_frames,
        memory_selector=memory_selector,
        _memory_uids=_memory_uids,
        _normal_form_validation=_normal_form_validation,
        _prompt_policy=resolve_semantic_prompt_policy(),
        _input_char_limit=ATOMIZE_INPUT_CHAR_LIMIT,
    )


__all__ = [name for name in globals() if not name.startswith("_")]
