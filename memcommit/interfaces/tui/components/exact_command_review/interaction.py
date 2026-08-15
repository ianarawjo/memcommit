"""Shared key contract for approving one focused exact-command review."""

from __future__ import annotations

from collections.abc import Callable

from prompt_toolkit.filters import FilterOrBool
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent

from memcommit.interfaces.tui.core.keybindings import bind_case_insensitive_key


def bind_exact_command_approval(
    bindings: KeyBindings,
    *,
    filter: FilterOrBool = True,
    legacy_a_filter: FilterOrBool | None = None,
    eager: FilterOrBool = True,
) -> Callable[
    [Callable[[KeyPressEvent], None]],
    Callable[[KeyPressEvent], None],
]:
    """Bind Enter as approval and retain A as a compatibility alias.

    ``filter`` must identify the focused final-review action.  A legacy shell
    that historically allowed A from a wider modal review may pass a separate
    ``legacy_a_filter`` while Enter remains limited to the visible receipt.
    The operation still owns the callback, frozen plan, and application rules.
    """

    def decorator(
        handler: Callable[[KeyPressEvent], None],
    ) -> Callable[[KeyPressEvent], None]:
        bindings.add("enter", filter=filter, eager=eager)(handler)
        bind_case_insensitive_key(
            bindings,
            "a",
            filter=(filter if legacy_a_filter is None else legacy_a_filter),
            eager=eager,
        )(handler)
        return handler

    return decorator


__all__ = ["bind_exact_command_approval"]
