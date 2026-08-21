"""Interface-independent requests and results for general and Ground Fit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memcommit.fit import FitReport
from memcommit.fit_judgment import FitAnalysis, FitProposition


@dataclass(frozen=True)
class FitPropositionsRequest:
    """Judge one complete role-neutral proposition set without persistence."""

    propositions: tuple[FitProposition, ...]
    background: tuple[FitProposition, ...] = ()

    def __post_init__(self) -> None:
        if len(self.propositions) < 2:
            raise ValueError("Fit requires at least two propositions.")
        if any(not isinstance(item, FitProposition) for item in self.propositions):
            raise TypeError("Fit propositions must be typed values.")
        if any(not isinstance(item, FitProposition) for item in self.background):
            raise TypeError("Fit background must contain typed values.")


@dataclass(frozen=True)
class FitMemorySourceRequest:
    """Select one direct Memory from the current or an explicit Context."""

    selector: str
    context_locator: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.selector, str) or not self.selector.strip():
            raise ValueError("A Fit Memory selector must be nonblank.")
        if self.context_locator is not None and (
            not isinstance(self.context_locator, str)
            or not self.context_locator.strip()
        ):
            raise ValueError("A Fit Memory Context locator must be nonblank.")


@dataclass(frozen=True)
class FitStoredSourcesRequest:
    """Resolve CLI operands and stored Memories into one general Fit frame."""

    propositions: tuple[FitProposition, ...]
    background: tuple[FitProposition, ...] = ()
    auto_operands: tuple[str, ...] = ()
    memory_sources: tuple[FitMemorySourceRequest, ...] = ()
    context_locators: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(item, FitProposition) for item in self.propositions):
            raise TypeError("Fit literal propositions must be typed values.")
        if any(not isinstance(item, FitProposition) for item in self.background):
            raise TypeError("Fit background must contain typed values.")
        if any(
            not isinstance(operand, str) or not operand.strip()
            for operand in self.auto_operands
        ):
            raise ValueError("Fit automatic operands must be nonblank text.")
        if any(
            not isinstance(item, FitMemorySourceRequest)
            for item in self.memory_sources
        ):
            raise TypeError("Fit Memory sources must be typed values.")
        if any(
            not isinstance(locator, str) or not locator.strip()
            for locator in self.context_locators
        ):
            raise ValueError("Fit Context locators must be nonblank.")
        if (
            not self.auto_operands
            and not self.memory_sources
            and not self.context_locators
        ):
            raise ValueError(
                "Stored-source Fit requires an automatic, Memory, or Context source."
            )


FitInputOriginKind = Literal["MEMORY", "CONTEXT"]


@dataclass(frozen=True)
class FitInputOrigin:
    """Exact stored origin for one frozen Memory proposition."""

    alias: str
    kind: FitInputOriginKind
    context_name: str
    context_uid: str
    memory_uid: str

    def __post_init__(self) -> None:
        if self.kind not in {"MEMORY", "CONTEXT"}:
            raise ValueError("Invalid Fit input origin kind.")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in (
                self.alias,
                self.context_name,
                self.context_uid,
                self.memory_uid,
            )
        ):
            raise ValueError("Fit input origin fields must be nonblank.")


@dataclass(frozen=True)
class FitPropositionsResult:
    """One read-only YES/MAY/NO Fit analysis."""

    analysis: FitAnalysis
    input_origins: tuple[FitInputOrigin, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, FitAnalysis):
            raise TypeError("Fit result requires a typed proposition analysis.")
        if any(
            not isinstance(item, FitInputOrigin) for item in self.input_origins
        ):
            raise TypeError("Fit result input origins must be typed values.")
        aliases = tuple(item.alias for item in self.input_origins)
        proposition_aliases = {
            item.alias for item in self.analysis.question.propositions
        }
        if len(aliases) != len(set(aliases)) or set(aliases) - proposition_aliases:
            raise ValueError(
                "Fit result input origins must uniquely name frozen propositions."
            )


@dataclass(frozen=True)
class FitRequest:
    """Ground graph adapter: run or reopen one immutable receipt."""

    ground_name: str
    receipt_uid: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ground_name, str) or not self.ground_name.strip():
            raise ValueError("Fit requires a saved Ground name.")
        if self.receipt_uid is not None and (
            not isinstance(self.receipt_uid, str) or not self.receipt_uid.strip()
        ):
            raise ValueError("Fit receipt uid must be nonblank when provided.")


@dataclass(frozen=True)
class FitResult:
    """One typed Fit report paired with an explicit freshness judgment."""

    report: FitReport
    current: bool

    def __post_init__(self) -> None:
        if not isinstance(self.report, FitReport):
            raise TypeError("Fit result requires a typed Fit report.")
        if type(self.current) is not bool:
            raise TypeError("Fit freshness must be a boolean.")
