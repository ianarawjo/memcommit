"""Connect the canonical English operation catalog to reviewed translations."""

from __future__ import annotations

from typing import Literal

from memcommit.application.operations.operation_catalog.catalog import operation_help
from memcommit.application.operations.operation_catalog.translations.fr import (
    TRANSLATIONS as FR_TRANSLATIONS,
)
from memcommit.application.operations.operation_catalog.translations.ko import (
    TRANSLATIONS as KO_TRANSLATIONS,
)
from memcommit.application.operations.operation_catalog.translations.mn import (
    TRANSLATIONS as MN_TRANSLATIONS,
)
from memcommit.application.operations.operation_catalog.translations.model import (
    LocalizedOperationCopy,
)
from memcommit.application.operations.operation_catalog.translations.zh import (
    TRANSLATIONS as ZH_TRANSLATIONS,
)


OperationCatalogLanguage = Literal["EN", "FR", "ZH", "KO", "MN"]

OPERATION_CATALOG_LANGUAGES: tuple[OperationCatalogLanguage, ...] = (
    "EN",
    "FR",
    "ZH",
    "KO",
    "MN",
)

OPERATION_TRANSLATIONS: dict[
    OperationCatalogLanguage,
    dict[str, LocalizedOperationCopy],
] = {
    "EN": {},
    "FR": FR_TRANSLATIONS,
    "ZH": ZH_TRANSLATIONS,
    "KO": KO_TRANSLATIONS,
    "MN": MN_TRANSLATIONS,
}


def localized_operation_copy(
    language: OperationCatalogLanguage,
    operation_name: str,
) -> LocalizedOperationCopy:
    """Return one operation's canonical or reviewed localized catalog copy."""

    canonical = operation_help(operation_name)
    english = LocalizedOperationCopy(canonical.summary, canonical.best_for)
    if language == "EN":
        return english
    return OPERATION_TRANSLATIONS[language].get(operation_name, english)


def validate_operation_translation_coverage(operation_names: set[str]) -> None:
    """Fail closed when a language catalog drifts from canonical operations."""

    for language in OPERATION_CATALOG_LANGUAGES:
        if language == "EN":
            continue
        translated = set(OPERATION_TRANSLATIONS[language])
        if translated != operation_names:
            missing = sorted(operation_names - translated)
            stale = sorted(translated - operation_names)
            raise ValueError(
                f"Operation catalog {language} translation coverage mismatch: "
                f"missing={missing}; stale={stale}"
            )
        if any(
            not copy.summary.strip() or not copy.best_for.strip()
            for copy in OPERATION_TRANSLATIONS[language].values()
        ):
            raise ValueError(f"Operation catalog {language} translation is blank.")


__all__ = [
    "OPERATION_CATALOG_LANGUAGES",
    "LocalizedOperationCopy",
    "OperationCatalogLanguage",
    "localized_operation_copy",
    "validate_operation_translation_coverage",
]
