"""Click-context compatibility for the shared command wait inventory."""

from memcommit.commands.help_inventory.command import CommandEntry
from memcommit.interfaces.tui.components import session_help


def test_help_inventory_uses_the_vendored_click_context_helper(monkeypatch):
    root = type("RootContext", (), {"parent": None})()
    child = type("ChildContext", (), {"parent": root})()
    seen = []
    expected = (
        CommandEntry(
            name="add",
            annotation=None,
            description="add description",
            command=object(),
            forms=("mem add", "mem add [value]"),
        ),
    )

    monkeypatch.setattr(
        session_help,
        "get_current_context",
        lambda *, silent: child if silent else None,
    )
    monkeypatch.setattr(
        session_help,
        "command_entries",
        lambda context: seen.append(context) or expected,
    )

    assert session_help.current_help_entries() == expected
    assert seen == [root]
