"""Provider selection for whole-corpus ordinary Query execution."""

from __future__ import annotations

from memcommit.config import Config
from memcommit.provider_types import CODEX_CHATGPT_PROVIDER, SemanticProvider
from memcommit.query_provider import (
    CodexChatGPTProvider,
    connect_query_provider as _connect_configured_query_provider,
)
from memcommit.study_action_log import (
    record_provider_connection_finished,
    record_provider_connection_started,
)


ORDINARY_QUERY_MODEL = "gpt-5.6-sol"
ORDINARY_QUERY_REASONING_EFFORT = "none"


def connect_ordinary_query_provider() -> CodexChatGPTProvider:
    """Connect the pinned Sol/none provider with shared auth and timeout."""

    operation = "query"
    started_at = record_provider_connection_started(operation)
    try:
        provider = CodexChatGPTProvider.connect(
            timeout=Config().semantic_timeout_seconds(),
            model=ORDINARY_QUERY_MODEL,
            reasoning_effort=ORDINARY_QUERY_REASONING_EFFORT,
        )
    except BaseException as error:
        record_provider_connection_finished(
            operation,
            started_at,
            failure=error,
        )
        raise
    record_provider_connection_finished(
        operation,
        started_at,
        provider=provider.identity.provider,
    )
    return provider


def connect_query_route_provider(provider_id: str) -> SemanticProvider:
    """Pin Codex Query without overriding an authorized non-Codex route."""

    if provider_id == CODEX_CHATGPT_PROVIDER:
        return connect_ordinary_query_provider()
    return _connect_configured_query_provider(provider_id)  # type: ignore[return-value]
