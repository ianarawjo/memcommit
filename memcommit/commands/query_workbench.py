"""Compatibility exports for the interface-owned Query workbench."""

from memcommit.interfaces.tui.operations.query import (
    GrantedQueryRunner,
    OrdinaryQueryRunner,
    QUERY_VIEW_LABEL,
    QueryAnswerClipboardProjection,
    QueryAnswerFocus,
    QueryWorkbenchResponse,
    QueryWorkbenchResult,
    project_query_answer_clipboard,
    query_answer_reference_document,
    query_answer_stop_count,
    render_query_answer,
    render_query_answer_fragments,
    run_query_workbench,
)

__all__ = [
    "GrantedQueryRunner",
    "OrdinaryQueryRunner",
    "QUERY_VIEW_LABEL",
    "QueryAnswerClipboardProjection",
    "QueryAnswerFocus",
    "QueryWorkbenchResponse",
    "QueryWorkbenchResult",
    "project_query_answer_clipboard",
    "query_answer_reference_document",
    "query_answer_stop_count",
    "render_query_answer",
    "render_query_answer_fragments",
    "run_query_workbench",
]
