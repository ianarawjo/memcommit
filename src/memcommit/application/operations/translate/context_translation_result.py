"""Typed result shared by the two Translate Context-write modes."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.core.context import Context

from .runtime import AppliedTranslation, TranslationPlan


@dataclass(frozen=True)
class ContextTranslationResult:
    """Exact destination and Source-to-result mappings published by Translate."""

    plan: TranslationPlan
    destination: Context
    translations: tuple[AppliedTranslation, ...]
    created_context: bool
