"""Global configuration for mem (~/.mem/config.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from memcommit.infrastructure.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_PROVIDER_PRESETS,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
)

CONFIG_FILE = Path.home() / ".mem" / "config.json"


class Config:

    def __init__(self):
        CONFIG_FILE.parent.mkdir(exist_ok=True)
        if not CONFIG_FILE.exists():
            self._write({})

    def _read(self) -> dict:
        with open(CONFIG_FILE) as f:
            return json.load(f)

    def _write(self, data: dict) -> None:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def get(self, key: str) -> Optional[str]:
        return self._read().get(key)

    def set(self, key: str, value: str) -> None:
        data = self._read()
        data[key] = value
        self._write(data)

    def update(self, values: dict[str, object]) -> None:
        """Write one coherent configuration change instead of partial keys."""
        data = self._read()
        data.update(values)
        self._write(data)

    def all(self) -> dict:
        return self._read()

    # --- Typed accessors ---

    def llm_model(self) -> Optional[str]:
        return self.get("llm_model")

    def require_llm_model(self) -> str:
        model = self.llm_model()
        if not model:
            raise RuntimeError(
                "No LLM model configured.\n"
                "Run: mem config set llm <model>   (e.g. llama3.2)\n"
                "Ollama must be running locally."
            )
        return model

    def semantic_provider(self) -> str:
        provider = self.get("semantic_provider") or CODEX_CHATGPT_PROVIDER
        if provider not in SEMANTIC_PROVIDER_IDS:
            raise RuntimeError(
                f"Unsupported semantic provider {provider!r}. Choose from: "
                + ", ".join(SEMANTIC_PROVIDER_IDS)
            )
        return provider

    def semantic_model(self) -> Optional[str]:
        return self.model_for_provider(self.semantic_provider())

    def model_for_provider(self, provider: str) -> Optional[str]:
        if provider == CODEX_CHATGPT_PROVIDER:
            return self.get(f"{CODEX_CHATGPT_PROVIDER}_model") or None
        provider_specific = self.get(f"{provider}_model")
        if provider_specific:
            return provider_specific
        # semantic_model is the compatibility key written by the first
        # provider-selection rollout. It belongs only to the currently active
        # provider and must not leak across an Ollama/OpenRouter switch.
        if self.get("semantic_provider") == provider:
            explicit = self.get("semantic_model")
            if explicit:
                return explicit
        if provider == OLLAMA_PROVIDER:
            return self.llm_model()
        return None

    def codex_reasoning_effort(self) -> Optional[str]:
        value = self.get(f"{CODEX_CHATGPT_PROVIDER}_reasoning_effort")
        if not value:
            return None
        normalized = str(value).strip().lower()
        if normalized not in CODEX_REASONING_EFFORTS:
            raise RuntimeError(
                "Configuration value 'codex_chatgpt_reasoning_effort' must be "
                + ", ".join(CODEX_REASONING_EFFORTS)
                + "."
            )
        return normalized

    def codex_preset(self) -> Optional[str]:
        value = self.get(f"{CODEX_CHATGPT_PROVIDER}_preset")
        if not value:
            return None
        normalized = str(value).strip().lower()
        if normalized not in CODEX_PROVIDER_PRESETS:
            raise RuntimeError(
                "Configuration value 'codex_chatgpt_preset' must be "
                + ", ".join(CODEX_PROVIDER_PRESETS)
                + "."
            )
        return normalized

    def require_semantic_model(self, provider: str | None = None) -> str:
        selected = provider or self.semantic_provider()
        model = self.model_for_provider(selected)
        if not model:
            raise RuntimeError(
                "No semantic model configured.\n"
                "Run: mem provider use ollama --model MODEL\n"
                "  or: mem provider use openrouter --model AUTHOR/MODEL"
            )
        return model

    def _positive_int(self, key: str, default: int) -> int:
        value = self.get(key)
        if value is None:
            return default
        try:
            parsed = int(value)
        except (TypeError, ValueError) as error:
            raise RuntimeError(f"Configuration value {key!r} is invalid.") from error
        if parsed < 1:
            raise RuntimeError(f"Configuration value {key!r} must be positive.")
        return parsed

    def semantic_context_tokens(self) -> int:
        return self._positive_int("semantic_context_tokens", 65_536)

    def semantic_max_output_tokens(self) -> int:
        return self._positive_int("semantic_max_output_tokens", 16_384)

    def semantic_timeout_seconds(self) -> float:
        return float(self._positive_int("semantic_timeout_seconds", 600))

    def semantic_thinking(self) -> bool | None:
        value = self.get("semantic_thinking")
        if value is None or str(value).strip().lower() == "auto":
            return None
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise RuntimeError(
            "Configuration value 'semantic_thinking' must be auto, true, or false."
        )

    def ollama_base_url(self) -> str:
        return self.get("ollama_base_url") or "http://127.0.0.1:11434"

    def openrouter_zdr(self) -> bool:
        value = self.get("openrouter_zdr")
        if value is None:
            return False
        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
        raise RuntimeError("Configuration value 'openrouter_zdr' is invalid.")
