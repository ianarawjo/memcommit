"""Static architecture-catalog completeness and reproducibility tests."""

from __future__ import annotations

from pathlib import Path

from scripts.callable_catalog.catalog import (
    build_catalog,
    render_callable_jsonl,
    render_operation_markdown,
    render_summary_json,
)
from memcommit.application.operations.operation_catalog import OPERATION_HELP_BY_NAME


REPOSITORY = Path(__file__).parents[1]
GENERATED = REPOSITORY / "agent-records" / "docs" / "generated"


def _snapshot():
    return build_catalog(REPOSITORY)


def test_callable_catalog_covers_every_source_module_and_declaration() -> None:
    snapshot = _snapshot()
    source_paths = tuple(sorted((REPOSITORY / "src" / "memcommit").rglob("*.py")))
    identifiers = [record.identifier for record in snapshot.callables]

    assert len(snapshot.source_modules) == len(source_paths)
    assert len(snapshot.callables) > len(source_paths)
    assert len(identifiers) == len(set(identifiers))
    assert {record.kind for record in snapshot.callables} == {
        "async-function",
        "class",
        "function",
        "lambda",
    }
    assert all(not Path(record.path).is_absolute() for record in snapshot.callables)
    assert all(record.line <= record.end_line for record in snapshot.callables)


def test_catalog_records_private_nested_and_inbound_call_evidence() -> None:
    snapshot = _snapshot()
    by_identifier = {record.identifier: record for record in snapshot.callables}
    operation_builder = by_identifier[
        "memcommit.application.operations.operation_catalog.catalog:_operation"
    ]

    assert operation_builder.visibility == "private"
    assert operation_builder.export_status == "not-exported"
    assert len(operation_builder.inbound_references) == len(OPERATION_HELP_BY_NAME)
    assert {reference.caller for reference in operation_builder.inbound_references} == {
        "memcommit.application.operations.operation_catalog.catalog:<module>"
    }
    assert any(record.visibility == "local" for record in snapshot.callables)


def test_operation_routes_cover_every_help_operation_and_cli_entry() -> None:
    snapshot = _snapshot()
    by_operation = {record.operation: record for record in snapshot.operations}

    assert set(by_operation) == set(OPERATION_HELP_BY_NAME)
    assert all(record.cli_entry != "MISSING" for record in snapshot.operations)
    assert by_operation["checkout"].cli_entry == (
        "memcommit.adapters.console.entrypoint:_checkout"
    )
    assert by_operation["embed"].cli_entry == (
        "memcommit.adapters.console.commands.embed:cmd"
    )


def test_operation_routes_keep_observed_shape_and_curated_conclusion_separate() -> None:
    snapshot = _snapshot()
    by_operation = {record.operation: record for record in snapshot.operations}

    assert (
        "memcommit.application.operations.pwd.application"
        in by_operation["pwd"].application_modules
    )
    assert (
        "memcommit.application.operations.summarize.application"
        in by_operation["summarize"].application_modules
    )
    assert not by_operation["summarize"].tui_modules
    assert "query_ordinary" in by_operation["query"].public_methods
    assert "memcommit.adapters.agent.query" in by_operation["query"].agent_modules
    for operation, public_method in (
        ("copy", "copy_memories"),
        ("move", "move_memories"),
    ):
        route = by_operation[operation]
        assert (
            "memcommit.application.operations.memory_transfer.application"
            in route.application_modules
        )
        assert (
            "memcommit.application.operations.memory_transfer.runtime"
            in route.application_modules
        )
        assert not route.tui_modules
        assert route.public_methods == (public_method,)
        assert route.agent_modules == ("memcommit.adapters.agent.memory_transfer",)
        assert route.curated_state == "CLOSED"
    assert by_operation["query"].curated_state == "CLOSED"
    assert by_operation["resolve"].curated_state == "CLOSED"
    assert by_operation["dedun"].curated_state == "CLOSED"
    assert by_operation["dedup"].curated_state == "CLOSED"
    assert by_operation["find"].curated_state == "CLOSED"
    assert by_operation["meld"].curated_state == "CLOSED"
    assert by_operation["compare"].curated_state == "CLOSED"
    assert by_operation["help"].curated_state == "CLOSED"
    assert by_operation["switch"].curated_state == "CLOSED"
    assert (
        "memcommit.application.operations.atomize.domain"
        in by_operation["atomize"].application_modules
    )
    assert (
        "memcommit.application.operations.compare.application"
        in by_operation["compare"].application_modules
    )
    for operation in ("dedup", "find-duplicates"):
        assert (
            "memcommit.application.operations.dedup.application"
            in by_operation[operation].application_modules
        )
    assert by_operation["dedup"].public_methods == ("dedup",)
    assert by_operation["find-duplicates"].public_methods == ("find_duplicates",)
    assert (
        "memcommit.application.operations.fit.judgment"
        in by_operation["fit"].application_modules
    )
    assert (
        "memcommit.application.operations.help.lookup_application"
        in by_operation["help"].application_modules
    )
    assert (
        "memcommit.application.operations.meld.sessions"
        in by_operation["meld"].application_modules
    )
    assert (
        "memcommit.application.operations.query.reference_application"
        in by_operation["query"].application_modules
    )
    assert (
        "memcommit.application.operations.sever.model"
        in by_operation["sever"].application_modules
    )
    assert (
        "memcommit.application.operations.translate.runtime"
        in by_operation["translate"].application_modules
    )
    assert (
        "memcommit.application.operations.translate.application"
        in by_operation["translate"].application_modules
    )
    assert (
        "memcommit.application.operations.translate.exchange_translations"
        in by_operation["translate"].application_modules
    )
    assert (
        "memcommit.application.operations.translate.create_translated_context"
        in by_operation["translate"].application_modules
    )
    assert (
        "memcommit.application.operations.chunk.application"
        in by_operation["chunk"].application_modules
    )
    assert (
        "memcommit.application.operations.clear.runtime"
        in by_operation["clear"].application_modules
    )
    assert (
        "memcommit.application.operations.contexts.runtime"
        in by_operation["contexts"].application_modules
    )
    assert (
        "memcommit.application.operations.undo.runtime"
        in by_operation["undo"].application_modules
    )
    assert (
        "memcommit.application.operations.redo.runtime"
        in by_operation["redo"].application_modules
    )
    assert (
        "memcommit.application.operations.distill.application"
        in by_operation["distill"].application_modules
    )
    assert (
        "memcommit.application.operations.distill.runtime"
        in by_operation["distill"].application_modules
    )
    assert (
        "memcommit.application.operations.elaborate.application"
        in by_operation["elaborate"].application_modules
    )
    assert (
        "memcommit.application.operations.elaborate.add_runtime"
        in by_operation["elaborate"].application_modules
    )
    assert (
        "memcommit.application.operations.show.application"
        in by_operation["show"].application_modules
    )
    assert "show" in by_operation["show"].public_methods
    assert "memcommit.adapters.agent.show" in by_operation["show"].agent_modules
    assert by_operation["show"].curated_state == "CLOSED"
    for operation in ("branch", "chunk", "clear", "contexts", "undo", "redo"):
        assert by_operation[operation].curated_state == "CLOSED"
    assert by_operation["translate"].curated_state == "CLOSED"
    assert {record.curated_state for record in snapshot.operations} == {
        "CLOSED",
        "MIXED",
        "UNREVIEWED",
    }


def test_curated_classification_covers_all_operations_conservatively() -> None:
    snapshot = _snapshot()
    states = {
        state: {
            record.operation
            for record in snapshot.operations
            if record.curated_state == state
        }
        for state in {record.curated_state for record in snapshot.operations}
    }

    classified = [
        operation for operations in states.values() for operation in operations
    ]

    # The authored classification registry owns route states and their totals.
    # This consumer checks coverage and representative evidence without copying
    # aggregate counts that become stale whenever another route is reviewed.
    assert set(classified) == set(OPERATION_HELP_BY_NAME)
    assert len(classified) == len(set(classified))
    assert {"embed", "forget", "reference"} <= states["CLOSED"]
    assert "update" in states["MIXED"]
    assert {"branch", "chunk", "clear", "contexts", "undo", "redo"} <= states["CLOSED"]
    assert "translate" in states["CLOSED"]
    assert "update" in states["MIXED"]


def test_checked_in_catalog_is_current() -> None:
    snapshot = _snapshot()
    expected = {
        "callable-catalog.jsonl": render_callable_jsonl(snapshot),
        "callable-catalog-summary.json": render_summary_json(snapshot),
        "operation-route-catalog.md": render_operation_markdown(snapshot),
    }

    # This generator owns a fixed output set.  Other generated documentation
    # may share the directory and must be verified by its own source registry.
    assert {
        name: (GENERATED / name).read_text(encoding="utf-8")
        for name in sorted(expected)
    } == expected
