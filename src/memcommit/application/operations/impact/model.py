"""Typed application catalog for operation-specific Impact routes.

Impact is one public operation whose supported children retain their owning
operation's prepare, authority, persistence, and Apply contracts. This module
owns only the complete route classification; console command installation and
rendering remain adapter responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ImpactLifecycle(str, Enum):
    """How an Impact route obtains the artifact that it projects."""

    PREPARE_PROCESS_LOCAL = "PREPARE_PROCESS_LOCAL"
    PREPARE_DURABLE = "PREPARE_DURABLE"
    PREPARE_OR_OPEN = "PREPARE_OR_OPEN"
    OPEN_SAVED = "OPEN_SAVED"


@dataclass(frozen=True)
class ImpactRoute:
    """One supported route and its operation-owned artifact lifecycle."""

    name: str
    lifecycle: ImpactLifecycle
    help: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name
            or self.name != self.name.casefold()
            or any(character.isspace() for character in self.name)
        ):
            raise ValueError("Impact route names must be lowercase command tokens.")
        if not isinstance(self.lifecycle, ImpactLifecycle):
            raise TypeError("Impact routes require a typed lifecycle.")
        if not isinstance(self.help, str) or not self.help.strip():
            raise ValueError("Impact routes require help text.")


@dataclass(frozen=True)
class DeferredImpactRoute:
    """A semantically eligible route whose adapter is not ready to register."""

    name: str
    reason: str


@dataclass(frozen=True)
class ExcludedImpactOperation:
    """A semantic boundary that must not become an Impact route."""

    name: str
    reason: str


class ImpactRouteCatalog:
    """Validate the complete supported, deferred, and excluded Impact set."""

    def __init__(
        self,
        routes: tuple[ImpactRoute, ...],
        *,
        deferred: tuple[DeferredImpactRoute, ...] = (),
        excluded: tuple[ExcludedImpactOperation, ...] = (),
    ) -> None:
        route_names = tuple(route.name for route in routes)
        deferred_names = tuple(route.name for route in deferred)
        excluded_names = tuple(operation.name for operation in excluded)
        all_names = (*route_names, *deferred_names, *excluded_names)
        if len(set(all_names)) != len(all_names):
            raise ValueError("Impact catalog entries must have distinct names.")
        self._routes = routes
        self._deferred = deferred
        self._excluded = excluded

    @property
    def routes(self) -> tuple[ImpactRoute, ...]:
        return self._routes

    @property
    def deferred(self) -> tuple[DeferredImpactRoute, ...]:
        return self._deferred

    @property
    def excluded(self) -> tuple[ExcludedImpactOperation, ...]:
        return self._excluded

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(route.name for route in self._routes)

    def route(self, name: str) -> ImpactRoute:
        matches = tuple(route for route in self._routes if route.name == name)
        if len(matches) != 1:
            raise KeyError(f"No registered Impact route matches '{name}'.")
        return matches[0]


IMPACT_ROUTES = ImpactRouteCatalog(
    (
        ImpactRoute(
            "atomize",
            ImpactLifecycle.PREPARE_DURABLE,
            "Preview or reopen one Context's saved Atomize analysis.",
        ),
        ImpactRoute(
            "forget",
            ImpactLifecycle.PREPARE_PROCESS_LOCAL,
            "Preview complete in-place Forget decisions without applying them.",
        ),
        ImpactRoute(
            "distill",
            ImpactLifecycle.PREPARE_PROCESS_LOCAL,
            "Preview the Rules Distill would add to an existing Target.",
        ),
        ImpactRoute(
            "elaborate",
            ImpactLifecycle.PREPARE_PROCESS_LOCAL,
            "Preview one append-only same-UID Memory revision.",
        ),
        ImpactRoute(
            "makemore",
            ImpactLifecycle.PREPARE_PROCESS_LOCAL,
            "Preview the unverified Memories Makemore would add.",
        ),
        ImpactRoute(
            "resolve",
            ImpactLifecycle.PREPARE_PROCESS_LOCAL,
            "Preview one exact verified Resolve candidate without applying it.",
        ),
        ImpactRoute(
            "meld",
            ImpactLifecycle.OPEN_SAVED,
            "Inspect one saved Meld assessment.",
        ),
        ImpactRoute(
            "sever",
            ImpactLifecycle.OPEN_SAVED,
            "Inspect one saved Sever result.",
        ),
        ImpactRoute(
            "update",
            ImpactLifecycle.PREPARE_OR_OPEN,
            "Preview a directional Update or inspect one saved Update plan.",
        ),
    ),
    deferred=(
        DeferredImpactRoute(
            "dedun",
            "The semantic review and candidate adapter are still being "
            "stabilized; Impact must not guess that artifact contract.",
        ),
    ),
    excluded=(
        ExcludedImpactOperation(
            "translate",
            "Translation changes representation rather than proposing a Memory "
            "state transition.",
        ),
        ExcludedImpactOperation(
            "ground",
            "Ground uses exact-command approval and must not be reduced to a "
            "generic Impact artifact.",
        ),
    ),
)


__all__ = [
    "DeferredImpactRoute",
    "ExcludedImpactOperation",
    "IMPACT_ROUTES",
    "ImpactLifecycle",
    "ImpactRoute",
    "ImpactRouteCatalog",
]
