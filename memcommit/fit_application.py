"""Interface-independent request and result values for Fit."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.fit import FitReport


@dataclass(frozen=True)
class FitRequest:
    """Run Fit for one Ground or reopen one exact immutable receipt."""

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
