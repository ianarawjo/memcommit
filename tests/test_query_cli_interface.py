"""Contracts for Query's non-interactive CLI adapter boundary."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from memcommit.interfaces.cli.query import (
    render_granted_query_response,
    render_ordinary_query_response,
    render_query_reference_response,
    render_query_session,
    render_query_session_list,
    split_query_memory_selector,
)
from memcommit.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
)
from memcommit.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.operations.query.reference_application import (
    QueryReferenceRequest,
    QueryReferenceResponse,
)
from memcommit.query_sessions import AuthorityQueryCatalogEntry


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "memcommit"


def test_query_memory_selector_split_is_interface_owned_and_exact():
    assert split_query_memory_selector("shared/view") == ("shared/view", None)
    assert split_query_memory_selector("shared/view#q-0123456789ab") == (
        "shared/view",
        "q-0123456789ab",
    )
    assert split_query_memory_selector("shared/view#q-not-a-handle") == (
        "shared/view#q-not-a-handle",
        None,
    )


def test_query_plain_renderers_preserve_typed_answer_modes(capsys):
    ordinary_request = OrdinaryQueryRequest("What?", ("source",))
    render_ordinary_query_response(
        OrdinaryQueryResponse(
            ordinary_request,
            "SUMMARY\n  (no grounded answer found)",
            False,
        )
    )

    reference_request = QueryReferenceRequest(
        "source-uid",
        "source",
        "provider",
        "What?",
    )
    render_query_reference_response(
        QueryReferenceResponse(reference_request, "answer\x1btext")
    )

    assert capsys.readouterr().out == (
        "SUMMARY\n  (no grounded answer found)\nanswer�text\n"
    )


def test_granted_query_plain_renderer_keeps_catalog_opaque(capsys):
    target = GrantedQueryTarget("grant", "shared/view", "anchor", False)
    response = GrantedQueryResponse(
        GrantedQueryRequest(target, None),
        catalog=(
            AuthorityQueryCatalogEntry(
                "q-0123456789ab",
                ("◯ ◯◯", "◯◯"),
            ),
        ),
    )

    render_granted_query_response(response)

    output = capsys.readouterr().out
    assert "Query view Memories: shared/view" in output
    assert "[q-0123456789ab]" in output
    assert "◯ ◯◯" in output
    assert "source text is not present" in output


def test_query_session_renderers_use_only_visible_transcript_fields(capsys):
    session = SimpleNamespace(
        name="notes",
        binding=SimpleNamespace(requested_name="shared/view", language="en"),
        revision=2,
        turns=(
            SimpleNamespace(question="What?", answer="Visible answer."),
        ),
    )

    render_query_session_list(())
    render_query_session_list((session,))
    render_query_session(session)

    output = capsys.readouterr().out
    assert "No saved query sessions." in output
    assert "notes · view=shared/view · language=en · 1 turn(s) · revision 2" in output
    assert "Query session: notes" in output
    assert "Q1\nWhat?\nA1\nVisible answer." in output


def test_query_command_uses_cli_and_terminal_interfaces_without_local_presenters():
    path = PACKAGE / "commands" / "query.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    local_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "from memcommit.interfaces.cli.query import (" in source
    assert "from memcommit.interfaces.console.terminal import is_interactive_terminal" in source
    assert "_interactive_terminal" not in local_functions
    assert "_split_query_memory_selector" not in local_functions
    assert "_render_query_catalog" not in local_functions
    assert local_functions == {
        "_open_query_workbench",
        "_query_ordinary_context",
        "cmd",
    }


def test_query_cli_adapter_has_no_store_provider_or_command_dependency():
    path = PACKAGE / "interfaces" / "cli" / "query.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("memcommit.commands") for module in imports)
    assert "memcommit.store" not in imports
    assert not any("provider" in module for module in imports)
