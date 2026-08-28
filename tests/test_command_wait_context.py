"""Click-context compatibility for the shared command wait inventory."""

from memcommit.adapters.console.commands.help.command import CommandEntry
from memcommit.adapters.console.terminal.components import session_help


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
        "_entry_builder",
        lambda context: seen.append(context) or expected,
    )

    assert session_help.current_help_entries() == expected
    assert seen == [root]
