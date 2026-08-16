"""Interface-independent requests and results for general and Ground Fit."""

from __future__ import annotations

from dataclasses import dataclass

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
class FitPropositionsResult:
    """One read-only YES/MAY/NO Fit analysis."""

    analysis: FitAnalysis

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, FitAnalysis):
            raise TypeError("Fit result requires a typed proposition analysis.")


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
