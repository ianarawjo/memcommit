"""TTY browser contracts for ``mem ls`` and the shared Context tree."""

from __future__ import annotations

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.list_memories import _snapshot_browser_tree


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_tty_ls_roots_shared_browser_at_exact_context(
    isolated_store,
    monkeypatch,
):
    invoke("init", "root")
    invoke("add", "root memory")
    invoke("init", "root/child")
    invoke("add", "child memory")
    observed: dict[str, object] = {}

    def browse(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return None

    monkeypatch.setattr(
        "memcommit.commands.list_memories._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.list_memories.choose_context",
        browse,
    )

    result = invoke("ls", "root")

    assert result.exit_code == 0
    assert len(observed["names"]) == 2
    root_id = observed["current"]
    assert observed["display_names"][root_id] == "root"
    assert set(observed["display_names"].values()) == {"root", "root/child"}
    assert observed["browse_only"] is True
    assert observed["initially_expand_selected"] is True
    assert observed["initially_expand_all"] is False
    assert observed["initially_show_memories"] is True
    rows = observed["memory_loader"](root_id)
    assert [row.content for row in rows] == ["root memory"]


def test_tty_ls_recursive_starts_with_root_descendants_fully_expanded(
    isolated_store,
    monkeypatch,
):
    invoke("init", "root")
    invoke("init", "root/child")
    invoke("init", "root/child/deep")
    observed: dict[str, object] = {}

    def browse(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return None

    monkeypatch.setattr(
        "memcommit.commands.list_memories._interactive_terminal",
        lambda: True,
    )
    monkeypatch.setattr(
        "memcommit.commands.list_memories.choose_context",
        browse,
    )

    result = invoke("ls", "-R", "root")

    assert result.exit_code == 0
    assert len(observed["names"]) == 3
    assert set(observed["display_names"].values()) == {
        "root",
        "root/child",
        "root/child/deep",
    }
    assert observed["initially_expand_selected"] is False
    assert observed["initially_expand_all"] is True
    assert observed["initially_show_memories"] is True


def test_snapshot_browser_preserves_repeated_context_occurrences():
    repeated = {
        "kind": "context",
        "uid": "shared-uid",
        "name": "shared",
        "cycle": False,
        "children": [
            {"kind": "memory", "uid": "memory-uid", "content": "same"}
        ],
    }
    snapshot = {
        "context": {"uid": "root-uid", "name": "root"},
        "items": [repeated, dict(repeated)],
    }

    tree, names, virtual, labels, annotations, memories = (
        _snapshot_browser_tree(snapshot)
    )

    assert len(names) == 3
    assert virtual == ()
    assert list(labels.values()).count("shared") == 2
    assert len(tree.children_by_name[tree.roots[0]]) == 2
    shared_ids = tree.children_by_name[tree.roots[0]]
    assert [row.content for row in memories[shared_ids[0]]] == ["same"]
    assert [row.content for row in memories[shared_ids[1]]] == ["same"]
    assert annotations == {}
