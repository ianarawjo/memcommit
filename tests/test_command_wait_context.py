"""Click-context compatibility for the shared command wait inventory."""

from memcommit.commands import command_wait
from memcommit.commands.help_inventory import CommandEntry


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
        command_wait,
        "get_current_context",
        lambda *, silent: child if silent else None,
    )
    monkeypatch.setattr(
        command_wait,
        "command_entries",
        lambda context: seen.append(context) or expected,
    )

    assert command_wait._current_help_entries() == expected
    assert seen == [root]
