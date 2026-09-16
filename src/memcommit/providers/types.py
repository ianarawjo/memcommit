"""Provider-neutral contracts for one-shot semantic completions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


CODEX_CHATGPT_PROVIDER = "codex_chatgpt"
OLLAMA_PROVIDER = "ollama"
OPENROUTER_PROVIDER = "openrouter"
CODEX_LUNA_LOW_PRESET = "luna-low"
CODEX_LUNA_MODEL = "gpt-5.6-luna"
CODEX_REASONING_EFFORTS = (
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
)
CODEX_PROVIDER_PRESETS = (CODEX_LUNA_LOW_PRESET,)
SEMANTIC_PROVIDER_IDS = (
    CODEX_CHATGPT_PROVIDER,
    OLLAMA_PROVIDER,
    OPENROUTER_PROVIDER,
)


@dataclass(frozen=True)
class ProviderIdentity:
    """Immutable identity available before a provider sees semantic input."""

    provider: str
    model: str
    model_digest: str | None = None
    runtime: str | None = None
    endpoint: str | None = None
    reasoning_effort: str | None = None

    def display_name(self) -> str:
        label = f"{self.provider}:{self.model}"
        if self.model_digest:
            label += f"@{self.model_digest[:12]}"
        if self.reasoning_effort:
            label += f" · reasoning {self.reasoning_effort}"
        return label


@dataclass(frozen=True)
class CompletionRun:
    """Call metadata that contains no prompt or completion content."""

    identity: ProviderIdentity
    operation: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    upstream_model: str | None = None
    upstream_provider: str | None = None


class SemanticProvider(Protocol):
    """Smallest shared interface used by current semantic operations."""

    identity: ProviderIdentity
    timeout: float
    last_run: CompletionRun | None

    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Return one completion; callers retain semantic validation authority."""

    def query(self, source_name: str, source_content: str, question: str) -> str:
        """Answer from one opaque query-only source."""
