"""OpenRouterProvider request, authentication, and response handling."""

from __future__ import annotations

from dataclasses import dataclass, field

from memcommit.providers.errors import QueryProviderError
from memcommit.providers.http import JsonRequester, request_json
from memcommit.providers.types import (
    OPENROUTER_PROVIDER,
    CompletionRun,
    ProviderIdentity,
)
from memcommit.providers.clients.completion import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_OUTPUT_TOKENS,
    model_name,
    schema_instruction,
    usage_count,
    build_query_prompt,
)
from memcommit.persistence.command_ledger.study_actions import (
    record_study_provider_turn,
)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class OpenRouterProvider:
    """OpenRouter adapter with fixed model, strict parameters, and no fallback."""

    model: str
    api_key: str = field(repr=False)
    identity: ProviderIdentity = field(init=False)
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_output_tokens: int = DEFAULT_OUTPUT_TOKENS
    zdr: bool = False
    last_run: CompletionRun | None = field(default=None, init=False)
    _requester: JsonRequester = field(default=request_json, repr=False)

    def __post_init__(self) -> None:
        self.model = model_name(self.model)
        self.identity = ProviderIdentity(
            provider=OPENROUTER_PROVIDER,
            model=self.model,
            runtime="openrouter",
            endpoint=OPENROUTER_BASE_URL,
        )

    @classmethod
    def connect(
        cls,
        *,
        model: str,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_output_tokens: int = DEFAULT_OUTPUT_TOKENS,
        zdr: bool = False,
        requester: JsonRequester = request_json,
    ) -> "OpenRouterProvider":
        model = model_name(model)
        if not isinstance(api_key, str) or not api_key.strip():
            raise QueryProviderError("OPENROUTER_API_KEY is not set.")
        headers = {"Authorization": f"Bearer {api_key}"}
        # Authenticate before any command is allowed to open query-only source
        # material. This mirrors the existing Codex login preflight boundary.
        key_info = requester(
            OPENROUTER_BASE_URL + "/key",
            "GET",
            None,
            headers,
            min(timeout, 15),
            "OpenRouter authentication probe",
        )
        if not isinstance(key_info.get("data"), dict):
            raise QueryProviderError(
                "OpenRouter returned an invalid authentication response."
            )
        return cls(
            model=model,
            api_key=api_key,
            timeout=timeout,
            max_output_tokens=max_output_tokens,
            zdr=zdr,
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
            messages.append(
                {"role": "system", "content": schema_instruction(output_schema)}
            )
        messages.append({"role": "user", "content": prompt})
        provider_policy: dict[str, object] = {
            "allow_fallbacks": False,
            "require_parameters": output_schema is not None,
            "data_collection": "deny",
        }
        if self.zdr:
            provider_policy["zdr"] = True
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0,
            "max_tokens": self.max_output_tokens,
            "provider": provider_policy,
        }
        if output_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "memcommit_response",
                    "strict": True,
                    "schema": output_schema,
                },
            }
        response = self._requester(
            OPENROUTER_BASE_URL + "/chat/completions",
            "POST",
            payload,
            {"Authorization": f"Bearer {self.api_key}"},
            self.timeout,
            operation,
        )
        choices = response.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices else None
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise QueryProviderError(
                f"The OpenRouter {operation} operation returned no answer."
            )
        finish_reason = (
            choice.get("finish_reason") if isinstance(choice, dict) else None
        )
        if finish_reason == "length":
            raise QueryProviderError(
                f"The OpenRouter {operation} operation exhausted its output budget."
            )
        usage = response.get("usage")
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            prompt_tokens=usage_count(usage, "prompt_tokens"),
            completion_tokens=usage_count(usage, "completion_tokens"),
            upstream_model=(
                response.get("model")
                if isinstance(response.get("model"), str)
                else None
            ),
            upstream_provider=(
                response.get("provider")
                if isinstance(response.get("provider"), str)
                else None
            ),
        )
        return content.strip()

    def query(self, source_name: str, source_content: str, question: str) -> str:
        if not question.strip():
            raise QueryProviderError("Question must be non-empty.")
        return self.complete(
            build_query_prompt(source_name, source_content, question),
            operation="query",
        )
