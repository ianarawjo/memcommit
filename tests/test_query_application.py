"""Application-boundary contracts for terminal-independent ordinary Query."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import uuid

import pytest

from memcommit.context import Context, Memory
import memcommit.application.operations.query.ordinary_application as query_application
from memcommit.application.operations.query.ordinary_application import (
    FrozenOrdinaryQuerySource,
    OrdinaryQueryRequest,
    run_ordinary_query,
)
from memcommit.application.operations.query.ordinary_runtime import execute_ordinary_query
from memcommit.application.operations.search.model import SearchCandidate
from memcommit.persistence.store import MemoryStore


def _candidate(content: str = "One authorized answer fact.") -> SearchCandidate:
    memory = Memory(uid="memory-1", content=content)
    return SearchCandidate(
        candidate_id="c000001",
        kind="memory",
        context_uid="context-1",
        context_names=("notes",),
        item=memory,
        search_text=memory.content,
    )


class _Source:
    def __init__(self, candidates=(), *, label="notes"):
        self.candidates = tuple(candidates)
        self.label = label
        self.calls: list[OrdinaryQueryRequest] = []

    def freeze(self, request):
        self.calls.append(request)
        return FrozenOrdinaryQuerySource(self.label, self.candidates)


class _AnsweringProvider:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        self.calls += 1
        assert operation == "ordinary query"
        payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
        aliases = [item["alias"] for item in payload["complete_frozen_corpus"]]
        return json.dumps(
            {
                "outcome_kind": "ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "The frozen evidence supports the answer.",
                        "source_aliases": aliases,
                    }
                ],
            }
        )


def test_run_ordinary_query_freezes_then_answers_once_without_terminal():
    request = OrdinaryQueryRequest(
        "What does the evidence support?",
        ("notes",),
        include_descendants=False,
        follow_embeds=False,
    )
    source = _Source((_candidate(),))
    provider = _AnsweringProvider()
    stages = []

    response = run_ordinary_query(
        request,
        source_port=source,
        provider_factory=lambda: provider,
        observer=stages.append,
    )

    assert source.calls == [request]
    assert provider.calls == 1
    assert stages == ["INPUTS_FROZEN", "CONNECTING_PROVIDER", "ANSWERING"]
    assert response.request == request
    assert response.grounded is True
    assert response.reference_document is not None
    assert response.answer == response.reference_document.text
    assert "The frozen evidence supports the answer. [1]" in response.answer


def test_empty_frozen_query_returns_without_constructing_provider():
    events = []

    class Source(_Source):
        def freeze(self, request):
            events.append("freeze")
            return super().freeze(request)

    def provider_factory():
        events.append("provider")
        raise AssertionError("An empty authorized frame needs no provider.")

    response = run_ordinary_query(
        OrdinaryQueryRequest("Anything?", ("empty",)),
        source_port=Source(label="empty"),
        provider_factory=provider_factory,
    )

    assert events == ["freeze"]
    assert response.grounded is False
    assert response.answer == "empty\n  (no grounded answer found)"


@pytest.mark.parametrize(
    ("provider_response", "expected_answer", "grounded"),
    [
        (
            {
                "outcome_kind": "PARTIAL_ANSWER",
                "blocks": [
                    {
                        "role": "SUPPORTED_CLAIM",
                        "text": "The stored part is supported.",
                        "source_aliases": ["m1"],
                    },
                    {
                        "role": "SCOPE_LIMITATION",
                        "text": "The other part is absent from the selected Context.",
                        "source_aliases": [],
                    },
                ],
            },
            (
                "The stored part is supported. [1] The other part is absent "
                "from the selected Context."
            ),
            True,
        ),
        (
            {
                "outcome_kind": "NO_RELATED_OBSERVATION",
                "blocks": [
                    {
                        "role": "INPUT_INTERPRETATION",
                        "text": "This is a statement rather than a question.",
                        "source_aliases": [],
                    },
                    {
                        "role": "SCOPE_LIMITATION",
                        "text": "No directly related content is in this Context.",
                        "source_aliases": [],
                    },
                ],
            },
            (
                "This is a statement rather than a question. No directly "
                "related content is in this Context."
            ),
            False,
        ),
    ],
)
def test_application_preserves_partial_and_non_question_outcomes(
    provider_response,
    expected_answer,
    grounded,
):
    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            return json.dumps(provider_response)

    response = run_ordinary_query(
        OrdinaryQueryRequest("input", ("notes",)),
        source_port=_Source((_candidate(),)),
        provider_factory=Provider,
    )

    assert response.grounded is grounded
    assert expected_answer in response.answer
    assert ("References" in response.answer) is grounded


def test_whole_frame_preflight_fails_before_provider_construction(monkeypatch):
    events = []

    def reject(_question, _evidence):
        events.append("preflight")
        raise RuntimeError("whole frame is too large")

    def provider_factory():
        events.append("provider")
        return object()

    monkeypatch.setattr(query_application, "prepare_ordinary_query_answer", reject)

    with pytest.raises(RuntimeError, match="whole frame"):
        run_ordinary_query(
            OrdinaryQueryRequest("Anything?", ("notes",)),
            source_port=_Source((_candidate(),)),
            provider_factory=provider_factory,
        )

    assert events == ["preflight"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"question": "", "target_names": ("notes",)},
        {"question": "question", "target_names": ()},
        {"question": "question", "target_names": ("notes", "notes")},
        {
            "question": "question",
            "target_names": ("notes",),
            "include_descendants": 1,
        },
    ],
)
def test_ordinary_query_request_rejects_ambiguous_inputs(kwargs):
    with pytest.raises(ValueError):
        OrdinaryQueryRequest(**kwargs)


def test_runtime_executes_exact_scope_without_output_or_source_mutation(
    isolated_store,
    capsys,
):
    store = MemoryStore()
    root = Context(uid=str(uuid.uuid4()), name="task")
    root.add(Memory(uid="root-memory", content="Root-only fact."))
    child = Context(uid=str(uuid.uuid4()), name="task/child")
    child.add(Memory(uid="child-memory", content="Child fact."))
    store.save(root)
    store.save(child)
    before = {
        name: store.load_direct(name).to_dict() for name in (root.name, child.name)
    }

    class Access:
        is_granted = False

    class Catalog:
        def list_context_names(self):
            return [root.name, child.name]

        def context_exists(self, name):
            return store.context_exists(name)

        def load_direct(self, name):
            return store.load_direct(name)

        def load(self, name):
            return store.load(name)

        def access_for(self, _name):
            return Access()

    class Provider(_AnsweringProvider):
        def complete(self, prompt, *, operation, output_schema=None):
            payload = json.loads(prompt.split("ORDINARY QUERY PAYLOAD:\n", 1)[1])
            assert [item["content"] for item in payload["complete_frozen_corpus"]] == [
                "Root-only fact."
            ]
            return super().complete(
                prompt,
                operation=operation,
                output_schema=output_schema,
            )

    response = execute_ordinary_query(
        OrdinaryQueryRequest(
            "What is in the root?",
            (root.name,),
            include_descendants=False,
            follow_embeds=False,
        ),
        store=store,
        catalog=Catalog(),
        provider_factory=Provider,
    )

    assert response.grounded is True
    assert capsys.readouterr() == ("", "")
    assert {
        name: store.load_direct(name).to_dict() for name in (root.name, child.name)
    } == before


def test_ordinary_query_application_and_runtime_have_no_interface_dependency():
    root = Path(__file__).parents[1]
    application = ast.parse(
        (root / "src/memcommit/application/operations/query/ordinary_application.py").read_text()
    )
    runtime = ast.parse(
        (root / "src/memcommit/application/operations/query/ordinary_runtime.py").read_text()
    )

    def imports(tree):
        values = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                values.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                values.append(node.module)
        return tuple(values)

    forbidden = ("typer", "prompt_toolkit", "memcommit.adapters.console.commands")
    assert not any(name.startswith(forbidden) for name in imports(application))
    assert not any(name.startswith(forbidden) for name in imports(runtime))
    assert "memcommit.store" not in imports(application)
    assert "memcommit.query_provider" not in imports(application)
    assert "memcommit.query_provider" not in imports(runtime)


def test_production_adapters_import_ordinary_query_from_new_owner():
    root = Path(__file__).parents[1]
    command = (root / "src/memcommit/adapters/console/commands/query/command.py").read_text()
    workbench_model = (
        root / "src/memcommit/adapters/interfaces/tui/operations/query/model.py"
    ).read_text()

    assert (
        "from memcommit.application.operations.query.ordinary_application import "
        "OrdinaryQueryRequest" in command
    )
    assert (
        "from memcommit.application.operations.query.ordinary_runtime import "
        "execute_ordinary_query" in command
    )
    assert (
        "from memcommit.application.operations.query.ordinary_application import ("
        in workbench_model
    )
