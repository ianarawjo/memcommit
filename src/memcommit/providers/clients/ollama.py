"""OllamaProvider request, authentication, and response handling."""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field

from memcommit.providers.errors import QueryProviderError
from memcommit.providers.http import JsonRequester, request_json
from memcommit.providers.types import OLLAMA_PROVIDER, CompletionRun, ProviderIdentity
from memcommit.providers.clients.completion import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_OUTPUT_TOKENS,
    model_name,
    schema_instruction,
    usage_count,
    build_query_prompt,
)
from memcommit.persistence.command_ledger.study_actions import (
    record_study_provider_turn,
)

OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _loopback_ollama_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise QueryProviderError(
            "The Ollama endpoint must be a plain loopback HTTP origin."
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise QueryProviderError("The Ollama endpoint port is invalid.") from error
    host = "[::1]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}{':' + str(port) if port is not None else ''}"


@dataclass
class OllamaProvider:
    """Tool-less local completion adapter with schema-constrained generation."""

    model: str
    base_url: str
    identity: ProviderIdentity
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    context_tokens: int = DEFAULT_CONTEXT_TOKENS
    max_output_tokens: int = DEFAULT_OUTPUT_TOKENS
    thinking: bool = False
    last_run: CompletionRun | None = field(default=None, init=False)
    _requester: JsonRequester = field(default=request_json, repr=False)

    @classmethod
    def connect(
        cls,
        *,
        model: str,
        base_url: str = OLLAMA_DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        context_tokens: int = DEFAULT_CONTEXT_TOKENS,
        max_output_tokens: int = DEFAULT_OUTPUT_TOKENS,
        thinking: bool | None = None,
        requester: JsonRequester = request_json,
    ) -> "OllamaProvider":
        model = model_name(model)
        base_url = _loopback_ollama_base_url(base_url)
        version = requester(
            base_url + "/api/version",
            "GET",
            None,
            {},
            min(timeout, 10),
            "Ollama version probe",
        ).get("version")
        tags = requester(
            base_url + "/api/tags",
            "GET",
            None,
            {},
            min(timeout, 10),
            "Ollama model probe",
        ).get("models")
        if not isinstance(tags, list):
            raise QueryProviderError("Ollama returned an invalid model catalog.")
        match = next(
            (
                item
                for item in tags
                if isinstance(item, dict) and item.get("name") == model
            ),
            None,
        )
        if match is None:
            raise QueryProviderError(f"Ollama model {model!r} is not installed.")
        shown = requester(
            base_url + "/api/show",
            "POST",
            {"model": model},
            {},
            min(timeout, 10),
            "Ollama capability probe",
        )
        capabilities = shown.get("capabilities")
        supports_thinking = (
            isinstance(capabilities, list) and "thinking" in capabilities
        )
        if thinking is True and not supports_thinking:
            raise QueryProviderError(
                f"Ollama model {model!r} does not advertise thinking support."
            )
        effective_thinking = supports_thinking if thinking is None else thinking
        digest = match.get("digest")
        return cls(
            model=model,
            base_url=base_url,
            identity=ProviderIdentity(
                provider=OLLAMA_PROVIDER,
                model=model,
                model_digest=(digest if isinstance(digest, str) else None),
                runtime=(
                    f"ollama/{version}"
                    if isinstance(version, str) and version
                    else "ollama"
                ),
                endpoint=base_url,
            ),
            timeout=timeout,
            context_tokens=context_tokens,
            max_output_tokens=max_output_tokens,
            thinking=effective_thinking,
            _requester=requester,
        )

    @record_study_provider_turn
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        messages: list[dict[str, str]] = []
        if output_schema is not None:
            # Some local models accept a grammar but do not reliably apply its
            # semantic field constraints. Mirroring the trusted schema in the
            # system message makes the constraint explicit without weakening
            # the operation's existing local parser.
            messages.append(
                {"role": "system", "content": schema_instruction(output_schema)}
            )
        messages.append({"role": "user", "content": prompt})
        options: dict[str, object] = {
            "temperature": 0,
            "num_ctx": self.context_tokens,
            "num_predict": self.max_output_tokens,
        }
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.thinking,
            "options": options,
        }
        if output_schema is not None:
            payload["format"] = output_schema
        response = self._requester(
            self.base_url + "/api/chat",
            "POST",
            payload,
            {},
            self.timeout,
            operation,
        )
        message = response.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise QueryProviderError(
                f"The Ollama {operation} operation returned no answer."
            )
        if response.get("done_reason") == "length":
            raise QueryProviderError(
                f"The Ollama {operation} operation exhausted its output budget."
            )
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=usage_count(response, "prompt_eval_count"),
            completion_tokens=usage_count(response, "eval_count"),
            upstream_model=(
                response.get("model")
                if isinstance(response.get("model"), str)
                else None
            ),
            upstream_provider="ollama",
        )
        return content.strip()

    def query(self, source_name: str, source_content: str, question: str) -> str:
        if not question.strip():
            raise QueryProviderError("Question must be non-empty.")
        return self.complete(
            build_query_prompt(source_name, source_content, question),
            operation="query",
        )
