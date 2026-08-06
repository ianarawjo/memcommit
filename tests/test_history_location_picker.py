"""Shared Context-tree stage for Log and Diff checkpoint browsing."""
from __future__ import annotations

import memcommit.commands.history_location_picker as location_picker
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput

from memcommit.commands.context_picker import ContextSubtreeSelection


def test_location_picker_keeps_real_catalog_parents_as_unavailable_tree_rows(
    monkeypatch,
):
    observed = {}

    def choose(names, **kwargs):
        observed["names"] = names
        observed.update(kwargs)
        return names[0]

    monkeypatch.setattr(location_picker, "choose_context", choose)

    selected = location_picker.choose_history_location(
        ("task-1/campus-wiki/building-access",),
        current=None,
        annotations={
            "task-1/campus-wiki/building-access": "checkpoint abcdef12"
        },
        title="DIFF · SELECT A CONTEXT",
        catalog_names=(
            "task-1",
            "task-1/campus-wiki",
            "task-1/campus-wiki/building-access",
        ),
        require_tty=False,
    )

    assert selected == "task-1/campus-wiki/building-access"
    assert observed["names"] == ("task-1/campus-wiki/building-access",)
    assert observed["virtual_names"] == ("task-1", "task-1/campus-wiki")
    assert observed["accept_label"] == "open checkpoints"


def test_enter_selects_all_changed_descendants_from_namespace_parent():
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\r")
        selected = location_picker.choose_history_location(
            ("task-1/campus-wiki/building-access",),
            current="task-1/campus-wiki",
            annotations={
                "task-1/campus-wiki/building-access": "checkpoint abcdef12"
            },
            title="DIFF · SELECT A CONTEXT",
            catalog_names=(
                "task-1/campus-wiki",
                "task-1/campus-wiki/building-access",
            ),
            descendant_scope_names=("task-1/campus-wiki",),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert selected == ContextSubtreeSelection("task-1/campus-wiki")
