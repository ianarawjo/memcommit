"""TTY browser contracts for ``mem ls`` and the shared Context tree."""

from __future__ import annotations

from typer.testing import CliRunner

from memcommit.cli import app
from memcommit.commands.list_memories import _snapshot_browser_tree
from memcommit.source_projection.model import SourceReach


runner = CliRunner()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_tty_ls_uses_profile_catalog_with_exact_context_as_initial_row(
    isolated_store,
    monkeypatch,
):
    invoke("init", "outside")
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
    assert tuple(observed["names"]) == ("outside", "root", "root/child")
    assert observed["current"] == "root"
    assert observed["browse_only"] is True
    assert observed["initially_expand_selected"] is True
    assert observed["initially_expand_all"] is False
    assert observed["initially_expand_subtree_root"] is None
    assert observed["initially_show_memories"] is False
    assert observed["initially_show_memory_contexts"] == frozenset({"root"})
    assert observed["virtual_annotations"] == {}
    rows = observed["memory_loader"]("root")
    assert [row.content for row in rows] == ["root memory"]


def test_tty_ls_recursive_starts_with_root_descendants_fully_expanded(
    isolated_store,
    monkeypatch,
):
    invoke("init", "outside")
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
    assert tuple(observed["names"]) == (
        "outside",
        "root",
        "root/child",
        "root/child/deep",
    )
    assert observed["current"] == "root"
    assert observed["initially_expand_selected"] is False
    assert observed["initially_expand_all"] is False
    assert observed["initially_expand_subtree_root"] == "root"
    assert observed["initially_show_memories"] is False
    assert observed["initially_show_memory_contexts"] == frozenset(
        {"root", "root/child", "root/child/deep"}
    )


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

    (
        tree,
        names,
        virtual,
        labels,
        local_annotations,
        virtual_annotations,
        memories,
    ) = _snapshot_browser_tree(snapshot)

    assert len(names) == 3
    assert virtual == ()
    assert list(labels.values()).count("shared") == 2
    assert len(tree.children_by_name[tree.roots[0]]) == 2
    shared_ids = tree.children_by_name[tree.roots[0]]
    assert [row.content for row in memories[shared_ids[0]]] == ["same"]
    assert [row.content for row in memories[shared_ids[1]]] == ["same"]
    assert set(local_annotations) == set(shared_ids)
    assert virtual_annotations == {}
    assert all(
        annotation.reach is SourceReach.VIA_EMBED
        for annotation in local_annotations.values()
    )


def test_snapshot_browser_separates_materialized_and_virtual_annotations():
    snapshot = {
        "context": {"uid": "root-uid", "name": "root"},
        "items": [
            {
                "kind": "context",
                "uid": "child-uid",
                "name": "root/child",
                "cycle": False,
                "children": [],
            },
            {
                "kind": "query_context_ref",
                "uid": "query-uid",
                "name": "root/query",
            },
        ],
    }

    (
        _tree,
        names,
        virtual,
        _labels,
        local_annotations,
        virtual_annotations,
        _memories,
    ) = _snapshot_browser_tree(snapshot)

    assert set(local_annotations) <= set(names)
    assert set(virtual_annotations) == set(virtual)
    assert set(local_annotations).isdisjoint(virtual_annotations)
