"""Typed command registry for operation-specific Impact routes.

The registry owns discovery and CLI composition only.  Each registered handler
must still enter the owning operation's prepare/project boundary; this module
does not provide a common provider, authority, persistence, or Apply lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

import typer


class ImpactLifecycle(str, Enum):
    """How an Impact route obtains the artifact that it projects."""

    PREPARE_PROCESS_LOCAL = "PREPARE_PROCESS_LOCAL"
    PREPARE_DURABLE = "PREPARE_DURABLE"
    PREPARE_OR_OPEN = "PREPARE_OR_OPEN"
    OPEN_SAVED = "OPEN_SAVED"


@dataclass(frozen=True)
class ImpactRoute:
    """One supported named route and its operation-owned artifact lifecycle."""

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
    """An explicit semantic boundary that must not become an Impact route."""

    name: str
    reason: str


class ImpactRouteRegistry:
    """Validate and install the complete supported named Impact command set."""

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
            raise ValueError("Impact registry entries must have distinct names.")
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

    def install(
        self,
        app: typer.Typer,
        handlers: Mapping[str, Callable[..., None]],
    ) -> None:
        """Install only an exact handler set so Help cannot drift from routing."""

        expected = set(self.names)
        supplied = set(handlers)
        if supplied != expected:
            missing = ", ".join(sorted(expected - supplied)) or "none"
            extra = ", ".join(sorted(supplied - expected)) or "none"
            raise ValueError(
                "Impact handler registry mismatch: "
                f"missing [{missing}], extra [{extra}]."
            )
        for route in self._routes:
            app.command(route.name, help=route.help)(handlers[route.name])


IMPACT_ROUTES = ImpactRouteRegistry(
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
            "Preview the unverified Memories Elaborate would add.",
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
    "ImpactRouteRegistry",
]
