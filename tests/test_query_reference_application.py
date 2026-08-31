"""Application boundary for legacy QueryContextRef reads."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from memcommit.application.operations.search_explain.retrieve_answer.query.reference_application import (
    FrozenQueryReferenceSource,
    QueryReferenceRequest,
    QueryReferenceResponse,
    run_query_reference,
)
from memcommit.application.operations.search_explain.retrieve_answer.query.reference_runtime import execute_query_reference
from memcommit.persistence.store import MemoryStore


def _request(**overrides) -> QueryReferenceRequest:
    values = {
        "source_uid": "2f6f6117-5b20-41b9-8f77-5012fdb8a56b",
        "source_name": "construction-details",
        "provider_name": "codex_chatgpt",
        "question": "What closes?",
        "language": "en",
    }
    values.update(overrides)
    return QueryReferenceRequest(**values)


def test_application_constructs_provider_before_opening_concealed_source():
    events: list[object] = []
    request = _request()

    class SourcePort:
        def open(self, frozen_request):
            events.append(("source", frozen_request))
            return FrozenQueryReferenceSource(
                "construction-details",
                "The rear entrance closes at 17:00.",
            )

    class Provider:
        def query(self, source_name, source_content, question):
            events.append(("query", source_name, source_content, question))
            return "The rear entrance closes."

    def provider_factory(provider_name):
        events.append(("provider", provider_name))
        return Provider()

    stages: list[str] = []
    response = run_query_reference(
        request,
        source_port=SourcePort(),
        provider_factory=provider_factory,
        observer=stages.append,
    )

    assert response == QueryReferenceResponse(
        request,
        "The rear entrance closes.",
    )
    assert events == [
        ("provider", "codex_chatgpt"),
        ("source", request),
        (
            "query",
            "construction-details",
            "The rear entrance closes at 17:00.",
            "What closes?",
        ),
    ]
    assert stages == ["CONNECTING_PROVIDER", "OPENING_SOURCE", "ANSWERING"]


def test_provider_failure_does_not_open_concealed_source():
    opened = False

    class SourcePort:
        def open(self, _request):
            nonlocal opened
            opened = True
            raise AssertionError("Source opened before provider construction")

    def unavailable(_provider_name):
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_query_reference(
            _request(),
            source_port=SourcePort(),
            provider_factory=unavailable,
        )
    assert opened is False


@pytest.mark.parametrize(
    "field",
    ["source_uid", "source_name", "provider_name", "question", "language"],
)
def test_request_rejects_blank_control_fields(field):
    with pytest.raises(ValueError, match="must be nonblank"):
        _request(**{field: " "})


def test_runtime_reads_exact_language_without_writing_or_printing(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    source = store.create_bilingual_query_source(
        "construction-details",
        entries=(
            {
                "key": "rear-entrance",
                "canonical_content": "The rear entrance is closed.",
                "translations": {"ko": "후문은 폐쇄된다."},
            },
            {
                "key": "hours",
                "canonical_content": "The main entrance closes at 17:00.",
                "translations": {"ko": "정문은 오후 5시에 닫힌다."},
            },
        ),
    )
    before = {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    }
    calls: list[tuple[str, str, str]] = []

    class Provider:
        def query(self, source_name, source_content, question):
            calls.append((source_name, source_content, question))
            return "후문과 정문입니다."

    response = execute_query_reference(
        _request(
            source_uid=source.uid,
            question="무엇이 닫히나요?",
            language="ko",
        ),
        store=store,
        provider_factory=lambda _provider_name: Provider(),
    )

    assert response.answer == "후문과 정문입니다."
    assert calls == [
        (
            "construction-details",
            "후문은 폐쇄된다.\n\n정문은 오후 5시에 닫힌다.",
            "무엇이 닫히나요?",
        )
    ]
    assert capsys.readouterr() == ("", "")
    assert {
        path.relative_to(isolated_store): path.read_bytes()
        for path in isolated_store.rglob("*")
        if path.is_file()
    } == before


def test_runtime_authenticates_before_rejecting_source_identity(isolated_store):
    store = MemoryStore()
    source = store.create_query_source(
        "construction-details",
        "Concealed content.",
    )
    events: list[str] = []

    class Provider:
        def query(self, *_args):
            raise AssertionError("An invalid Source identity must not be queried")

    def provider_factory(_provider_name):
        events.append("provider")
        return Provider()

    with pytest.raises(ValueError, match="identity"):
        execute_query_reference(
            _request(source_uid=source.uid, source_name="wrong-name"),
            store=store,
            provider_factory=provider_factory,
        )
    assert events == ["provider"]


def test_query_reference_modules_have_no_interface_or_concrete_provider_dependency():
    root = Path(__file__).parents[1]

    def imports(path: Path) -> tuple[str, ...]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        values: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                values.append(node.module)
        return tuple(values)

    application_imports = imports(
        root / "src/memcommit/application/operations/search_explain/retrieve_answer/query/reference_application.py"
    )
    runtime_imports = imports(
        root / "src/memcommit/application/operations/search_explain/retrieve_answer/query/reference_runtime.py"
    )
    forbidden = ("typer", "prompt_toolkit", "memcommit.adapters.console.commands")

    assert not any(name.startswith(forbidden) for name in application_imports)
    assert not any(name.startswith(forbidden) for name in runtime_imports)
    assert "memcommit.store" not in application_imports
    assert "memcommit.query_provider" not in application_imports
    assert "memcommit.query_provider" not in runtime_imports


def test_query_command_uses_reference_application_without_legacy_executor():
    command = (
        Path(__file__).parents[1] / "src/memcommit/adapters/console/commands/search_explain/retrieve_answer/query/command.py"
    ).read_text(encoding="utf-8")

    assert "from memcommit.application.operations.search_explain.retrieve_answer.query.reference_application import" in command
    assert "from memcommit.application.operations.search_explain.retrieve_answer.query.reference_runtime import" in command
    assert "def _query_legacy(" not in command
