"""Host-owned exact input coverage for staged semantic execution."""

from __future__ import annotations

from dataclasses import dataclass, field


class CoverageError(RuntimeError):
    """A staged execution omitted, duplicated, or invented an input identity."""


@dataclass
class InputCoverageLedger:
    """Record which frozen inputs completed exactly one provider batch."""

    expected_ids: tuple[str, ...]
    _seen: set[str] = field(default_factory=set, init=False, repr=False)

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in self.expected_ids):
            raise CoverageError("Semantic coverage ids must be nonempty text.")
        if len(self.expected_ids) != len(set(self.expected_ids)):
            raise CoverageError("Semantic coverage ids must be unique.")

    def record(self, values: tuple[str, ...]) -> None:
        if len(values) != len(set(values)):
            raise CoverageError("One semantic batch repeated an input id.")
        expected = set(self.expected_ids)
        unknown = set(values) - expected
        repeated = set(values) & self._seen
        if unknown:
            raise CoverageError("One semantic batch reported an unknown input id.")
        if repeated:
            raise CoverageError("Staged semantic execution repeated an input id.")
        self._seen.update(values)

    def finalize(self) -> None:
        if self._seen != set(self.expected_ids):
            raise CoverageError("Staged semantic execution did not cover every input.")
