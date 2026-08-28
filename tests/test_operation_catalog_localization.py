"""Localized operation catalog ownership and coverage."""

from __future__ import annotations

import pytest

from memcommit.application.operations.operation_catalog import OPERATION_HELP_BY_NAME
from memcommit.application.operations.operation_catalog.localization import (
    OPERATION_CATALOG_LANGUAGES,
    OperationCatalogLanguage,
    localized_operation_copy,
    validate_operation_translation_coverage,
)


def test_every_language_covers_the_canonical_operation_catalog() -> None:
    validate_operation_translation_coverage(set(OPERATION_HELP_BY_NAME))


def test_english_copy_comes_from_the_canonical_catalog() -> None:
    canonical = OPERATION_HELP_BY_NAME["atomize"]

    localized = localized_operation_copy("EN", "atomize")

    assert localized.summary == canonical.summary
    assert localized.best_for == canonical.best_for


@pytest.mark.parametrize(
    ("language", "summary_prefix"),
    (
        ("FR", "Atomiser immédiatement"),
        ("ZH", "立即将当前 Context 原子化"),
        ("KO", "현재 Context를 독립적으로"),
        ("MN", "Одоогийн Context-г тус тусад нь"),
    ),
)
def test_non_english_copy_is_selected_from_its_language_catalog(
    language: OperationCatalogLanguage,
    summary_prefix: str,
) -> None:
    assert language in OPERATION_CATALOG_LANGUAGES

    localized = localized_operation_copy(language, "atomize")

    assert localized.summary.startswith(summary_prefix)
    assert localized.best_for.strip()


def test_unknown_operation_is_rejected_by_the_canonical_catalog() -> None:
    with pytest.raises(KeyError, match="No Operation Help is registered"):
        localized_operation_copy("KO", "not-an-operation")
