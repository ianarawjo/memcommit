"""Contracts for Query's non-interactive CLI adapter boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from typer.testing import CliRunner

from memcommit.adapters.console.entrypoint import app
from memcommit.find_answer_references import (
    FindAnswerEvidence,
    FindAnswerSentence,
    build_find_answer_reference_document,
)
from memcommit.adapters.interfaces.cli.query import (
    render_granted_query_response,
    render_ordinary_query_response,
    render_query_reference_response,
)
from memcommit.application.operations.query.granted_application import (
    GrantedQueryRequest,
    GrantedQueryResponse,
    GrantedQueryTarget,
)
from memcommit.application.operations.query.ordinary_application import (
    OrdinaryQueryRequest,
    OrdinaryQueryResponse,
)
from memcommit.application.operations.query.reference_application import (
    QueryReferenceRequest,
    QueryReferenceResponse,
)


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "memcommit"
runner = CliRunner(mix_stderr=False)


def test_query_cli_has_no_transcript_session_surface():
    help_result = runner.invoke(app, ["query", "--help"])

    assert help_result.exit_code == 0
    assert "--session" not in help_result.output
    assert "--sessions" not in help_result.output
    assert "--show-session" not in help_result.output

    removed = runner.invoke(app, ["query", "--sessions"])
    assert removed.exit_code == 2
    assert "No such option" in (removed.output + removed.stderr)


def test_query_help_exposes_profile_wide_all_alias():
    result = runner.invoke(app, ["query", "--help"])

    assert result.exit_code == 0
    assert "--all" in result.output
    assert "-a" in result.output
    assert "all readable Contexts" in result.output
    assert "active Profile" in result.output


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
    granted_request = GrantedQueryRequest(
        GrantedQueryTarget("grant", "shared/view", "anchor"),
        "What?",
    )
    render_granted_query_response(
        GrantedQueryResponse(granted_request, "granted\x1banswer")
    )

    assert capsys.readouterr().out == (
        "SUMMARY\n  (no grounded answer found)\nanswer�text\ngranted�answer\n"
    )


def test_grounded_query_plain_renderer_uses_self_contained_reference_rows(capsys):
    request = OrdinaryQueryRequest("What?", ("left", "right"))
    document = build_find_answer_reference_document(
        (
            FindAnswerEvidence(
                "m1", "left/source", "memory", "11111111-left", "Left fact."
            ),
            FindAnswerEvidence(
                "m2", "right/source", "artifact", "22222222-right", "Right fact."
            ),
        ),
        (
            FindAnswerSentence("Combined answer.", ("m1", "m2")),
            FindAnswerSentence("No second claim."),
            FindAnswerSentence("No third claim."),
        ),
    )

    render_ordinary_query_response(
        OrdinaryQueryResponse(request, document.text, True, document)
    )

    assert capsys.readouterr().out == (
        "Combined answer. [1] [2] No second claim. No third claim.\n\n"
        "References\n"
        "[1] Left fact. — 11111111, left/source, m1\n"
        "[2] Right fact. — 22222222, right/source, m2\n"
    )


def test_query_command_uses_cli_and_terminal_interfaces_without_local_presenters():
    path = PACKAGE / "commands" / "query" / "command.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    local_functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "from memcommit.adapters.interfaces.cli.query import (" in source
    assert (
        "from memcommit.adapters.interfaces.console.terminal import is_interactive_terminal"
        in source
    )
    assert "_interactive_terminal" not in local_functions
    assert local_functions == {
        "_open_query_workbench",
        "_query_granted_target",
        "_query_ordinary_context",
        "_resolve_positional_query_target",
        "cmd",
    }


def test_query_cli_adapter_has_no_store_provider_or_command_dependency():
    path = PACKAGE / "adapters" / "interfaces" / "cli" / "query.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not any(module.startswith("memcommit.commands") for module in imports)
    assert "memcommit.store" not in imports
    assert not any("provider" in module for module in imports)
