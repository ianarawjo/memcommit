"""Navigation for the decision screen."""

from __future__ import annotations


from memcommit.adapters.console.terminal.components.action import render_action_button


def render_navigation(state, *, is_focused) -> list[tuple[str, str]]:
    if not state.items:
        return []
    position = f"{state.current_issue_index + 1} / {len(state.items)}"
    if not state.navigation_visible:
        return [("class:report-neutral", f" {position}\n")]
    focused = is_focused("navigation")
    fragments = [("", " ")]
    for index, option in enumerate(state.navigation.options):
        if index:
            fragments.append(("class:report-neutral", f"  {position}  "))
        fragments.extend(
            render_action_button(
                option.label,
                focused=focused and state.navigation.cursor_uid == option.uid,
            )
        )
    fragments.append(("", "\n"))
    return fragments
