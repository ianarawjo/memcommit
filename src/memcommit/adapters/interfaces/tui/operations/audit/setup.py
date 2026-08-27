"""Project Audit's single readable Source into shared endpoint setup."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.adapters.interfaces.tui.components.endpoint_setup import (
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    run_endpoint_setup,
)
from memcommit.source_projection.presentation import SourceDisplayValue


def audit_endpoint_setup_spec(
    names: Sequence[str],
    *,
    current: str,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
) -> EndpointSetupSpec:
    """Freeze Audit's one-direct-Context selection contract."""

    catalog = tuple(names)
    if (
        not catalog
        or len(set(catalog)) != len(catalog)
        or any(not isinstance(name, str) or not name for name in catalog)
    ):
        raise ValueError("Audit setup requires a distinct readable catalog.")
    if current not in catalog:
        raise ValueError("Audit setup current Context is outside the catalog.")
    labels = tuple((annotations or {}).items())
    return EndpointSetupSpec(
        title="MEM AUDIT · SOURCE",
        subtitle="CHOOSE ONE DIRECT CONTEXT",
        modes=(
            EndpointSetupMode(
                "AUDIT",
                "AUDIT · ONE DIRECT CONTEXT",
                "Choose one readable Source, then run the independent checks.",
            ),
        ),
        initial_mode_uid="AUDIT",
        roles=(
            EndpointSetupRole(
                "SOURCE",
                "SOURCE · ALL READABLE CONTEXTS",
                catalog,
                frozenset(catalog),
                current,
                current_context=current,
                annotations=labels,
                height=min(9, max(3, len(catalog))),
            ),
        ),
        action_label="RUN AUDIT",
    )


def choose_audit_setup(
    names: Sequence[str],
    *,
    current: str,
    annotations: Mapping[str, SourceDisplayValue] | None = None,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> str | None:
    """Return one process-local Source name without loading or mutating it."""

    draft = run_endpoint_setup(
        audit_endpoint_setup_spec(
            names,
            current=current,
            annotations=annotations,
        ),
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
    if draft is None:
        return None
    if draft.mode_uid != "AUDIT":
        raise ValueError("Audit setup returned an unsupported operation shape.")
    return draft.value("SOURCE").context_name
