"""Study-only exact-copy guard for natural-language Help lookup."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal, Sequence

from memcommit.application.operations.operation_catalog.model import OperationHelp
from memcommit.application.operations.profile.config import load_profile_registry, study_run_identity
from memcommit.adapters.interfaces.tui.operations.help.localization import (
    HELP_LANGUAGES,
    HelpLanguage,
    operation_copy,
)


STUDY_HELP_COPY_THRESHOLD_NUMERATOR = 1
STUDY_HELP_COPY_THRESHOLD_DENOMINATOR = 2
_TOKEN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[^\W_]+", re.UNICODE)


@dataclass(frozen=True)
class StudyHelpAuthoredField:
    """One visible authored Description or When value used by Help."""

    operation_name: str
    language: HelpLanguage
    kind: Literal["DESCRIPTION", "WHEN"]
    text: str


@dataclass(frozen=True)
class StudyHelpCopyMatch:
    """Content-free evidence that one request crossed the Study threshold."""

    operation_name: str
    language: HelpLanguage
    kind: Literal["DESCRIPTION", "WHEN"]
    exact_run_tokens: int
    authored_field_tokens: int


def _exact_tokens(value: str) -> tuple[str, ...]:
    normalized = unicodedata.normalize("NFKC", value).casefold().replace("_", " ")
    return tuple(_TOKEN.findall(normalized))


def _longest_exact_token_run(
    request_tokens: tuple[str, ...],
    authored_tokens: tuple[str, ...],
) -> int:
    """Return the longest contiguous token sequence shared by both values."""

    previous = [0] * (len(authored_tokens) + 1)
    longest = 0
    for request_token in request_tokens:
        current = [0]
        for index, authored_token in enumerate(authored_tokens, start=1):
            run = previous[index - 1] + 1 if request_token == authored_token else 0
            current.append(run)
            longest = max(longest, run)
        previous = current
    return longest


def authored_study_help_fields(
    operations: Sequence[OperationHelp],
) -> tuple[StudyHelpAuthoredField, ...]:
    """Freeze every localized Description/When value a participant can copy."""

    fields: list[StudyHelpAuthoredField] = []
    for operation in operations:
        for language in HELP_LANGUAGES:
            localized = operation_copy(
                language,
                operation.name,
                english_description=operation.summary,
                english_use_when=operation.best_for,
            )
            fields.extend(
                (
                    StudyHelpAuthoredField(
                        operation.name,
                        language,
                        "DESCRIPTION",
                        localized.description,
                    ),
                    StudyHelpAuthoredField(
                        operation.name,
                        language,
                        "WHEN",
                        localized.use_when,
                    ),
                )
            )
    return tuple(fields)


def find_study_help_copy_match(
    request: str,
    fields: Sequence[StudyHelpAuthoredField],
) -> StudyHelpCopyMatch | None:
    """Reject an exact contiguous run covering at least half one authored field."""

    request_tokens = _exact_tokens(request)
    if not request_tokens:
        return None
    for field in fields:
        authored_tokens = _exact_tokens(field.text)
        if not authored_tokens:
            continue
        longest = _longest_exact_token_run(request_tokens, authored_tokens)
        if (
            longest * STUDY_HELP_COPY_THRESHOLD_DENOMINATOR
            >= len(authored_tokens) * STUDY_HELP_COPY_THRESHOLD_NUMERATOR
        ):
            return StudyHelpCopyMatch(
                operation_name=field.operation_name,
                language=field.language,
                kind=field.kind,
                exact_run_tokens=longest,
                authored_field_tokens=len(authored_tokens),
            )
    return None


def active_profile_is_study() -> bool:
    """Use immutable init-study provenance, never a display-name heuristic."""

    registry = load_profile_registry()
    return study_run_identity(registry.active) is not None


__all__ = [
    "STUDY_HELP_COPY_THRESHOLD_DENOMINATOR",
    "STUDY_HELP_COPY_THRESHOLD_NUMERATOR",
    "StudyHelpAuthoredField",
    "StudyHelpCopyMatch",
    "active_profile_is_study",
    "authored_study_help_fields",
    "find_study_help_copy_match",
]
