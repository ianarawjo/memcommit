"""Selection flow used only when Share operands are incomplete in a TTY."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from memcommit.core.context_targeting.tui.picker import choose_context
from memcommit.application.operations.share.model import (
    ShareError,
    SharePreview,
    list_share_endpoints,
    list_share_sources,
    prepare_share,
)


ShareNameChooser = Callable[..., str | None]


class ShareFlowUnavailable(ShareError):
    """Bare Share can open, but no complete disclosure plan can be formed."""


def _choose_source(
    names: Sequence[str],
    *,
    current: str | None,
    chooser: ShareNameChooser,
) -> str | None:
    if not names:
        raise ShareFlowUnavailable(
            "No nonempty ordinary Context is available to share."
        )
    if len(names) == 1:
        return names[0]
    return chooser(
        tuple(names),
        current=current,
        title="Select a Context to share",
        accept_label="share this Context",
    )


def _choose_endpoint(
    names: Sequence[str],
    *,
    chooser: ShareNameChooser,
    current: str | None = None,
) -> str | None:
    if not names:
        raise ShareFlowUnavailable(
            "No SHARE endpoint is available to the active Profile."
        )
    # Initial setup may safely accept the only endpoint, but an explicit
    # in-view Browse request must still open the catalog it promised to show.
    if len(names) == 1 and current is None:
        return names[0]
    return chooser(
        tuple(names),
        current=current,
        title="Select a Share endpoint",
        accept_label="use endpoint",
        local_annotations={name: "SHARE ENDPOINT" for name in names},
    )


def choose_share_endpoint(
    *,
    current: str | None = None,
    chooser: ShareNameChooser = choose_context,
) -> str | None:
    """Browse the complete currently available SHARE endpoint catalog."""

    return _choose_endpoint(
        list_share_endpoints(),
        chooser=chooser,
        current=current,
    )


def choose_share_preview(
    source: str | None,
    recipient: str | None,
    *,
    include_descendants: bool = False,
    source_chooser: ShareNameChooser = choose_context,
    endpoint_chooser: ShareNameChooser = choose_context,
) -> SharePreview | None:
    """Fill missing operands locally, then freeze the final viewer projection."""

    selected_source = source
    if selected_source is None:
        current, names = list_share_sources(
            include_descendants=include_descendants,
        )
        selected_source = _choose_source(
            names,
            current=current,
            chooser=source_chooser,
        )
        if selected_source is None:
            return None

    selected_endpoint = recipient
    if not selected_endpoint:
        selected_endpoint = choose_share_endpoint(
            chooser=endpoint_chooser,
        )
        if selected_endpoint is None:
            return None

    return prepare_share(
        selected_source,
        selected_endpoint,
        include_descendants=include_descendants,
    )
