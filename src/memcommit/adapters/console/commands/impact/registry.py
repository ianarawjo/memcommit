"""Install application-owned Impact routes into the console command tree."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import typer

from memcommit.application.operations.impact import (
    DeferredImpactRoute,
    ExcludedImpactOperation,
    IMPACT_ROUTES,
    ImpactLifecycle,
    ImpactRoute,
    ImpactRouteCatalog,
)


def install_impact_routes(
    app: typer.Typer,
    handlers: Mapping[str, Callable[..., None]],
) -> None:
    """Install exactly the application-catalogued handler set."""

    expected = set(IMPACT_ROUTES.names)
    supplied = set(handlers)
    if supplied != expected:
        missing = ", ".join(sorted(expected - supplied)) or "none"
        extra = ", ".join(sorted(supplied - expected)) or "none"
        raise ValueError(
            "Impact handler registry mismatch: "
            f"missing [{missing}], extra [{extra}]."
        )
    for route in IMPACT_ROUTES.routes:
        app.command(route.name, help=route.help)(handlers[route.name])


__all__ = [
    "DeferredImpactRoute",
    "ExcludedImpactOperation",
    "IMPACT_ROUTES",
    "ImpactLifecycle",
    "ImpactRoute",
    "ImpactRouteCatalog",
    "install_impact_routes",
]
