"""Common application settings; project roots are registered per Profile."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from memcommit.llm_providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    OLLAMA_PROVIDER,
    SEMANTIC_PROVIDER_IDS,
)

from memcommit.configuration.workspace import (
    configuration_lock,
    read_configuration,
    require_workspace_ready,
    write_configuration,
    workspace_paths,
)

# An explicit override remains useful to embedding callers and isolated tests.
CONFIG_FILE: Path | None = None


class Config:
    def __init__(self):
        self._path_override = Path(CONFIG_FILE) if CONFIG_FILE is not None else None

    @property
    def path(self) -> Path:
        if self._path_override is not None:
            return self._path_override
        require_workspace_ready()
        return workspace_paths().workspace_dir / "config.json"

    def _read(self) -> dict:
        return read_configuration(self.path)

    def _write(self, data: dict) -> None:
        write_configuration(data, self.path)

    def get(self, key: str) -> Optional[str]:
        if key == "study_root_dir":
            return self._read().get(key, str(workspace_paths().workspace_dir / "studies"))
        return self._read().get(key)

    def set(self, key: str, value: str) -> None:
        if key in {"workspace_dir", "sync_base_dir"}:
            raise ValueError("Set Profile root_dir with mem profile config set root_dir PATH.")
        if key == "study_root_dir":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Study root must be a nonempty directory path.")
            value = str(Path(value).expanduser().resolve())
            if Path(value).exists() and not Path(value).is_dir():
                raise ValueError("Study root must be a directory.")
        with configuration_lock():
            data = self._read()
            data[key] = value
            self._write(data)

    def update(self, values: dict[str, object]) -> None:
        if {"workspace_dir", "sync_base_dir"} & values.keys():
            raise ValueError("Project locations belong to Profile configuration.")
        with configuration_lock():
            data = self._read()
            data.update(values)
            self._write(data)

    def all(self) -> dict:
        return {**self._read(), "study_root_dir": self.get("study_root_dir")}

    # --- Typed accessors ---

    def llm_model(self) -> Optional[str]:
        return self.get("llm_model")

    def semantic_provider(self) -> str:
        provider = self.get("semantic_provider") or CODEX_CHATGPT_PROVIDER
        if provider not in SEMANTIC_PROVIDER_IDS:
            raise RuntimeError(
                f"Unsupported semantic provider {provider!r}. Choose from: "
                + ", ".join(SEMANTIC_PROVIDER_IDS)
            )
        return provider

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
        values = self._read()
        key = f"{CODEX_CHATGPT_PROVIDER}_reasoning_effort"
        if key not in values:
            return "low"
        value = values[key]
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized not in CODEX_REASONING_EFFORTS:
            raise RuntimeError(
                "Configuration value 'codex_chatgpt_reasoning_effort' must be "
                + ", ".join(CODEX_REASONING_EFFORTS)
                + "."
            )
        return normalized

    def codex_service_tier(self) -> Optional[str]:
        value = self.get("codex_chatgpt_service_tier")
        if value is None:
            return "fast"
        normalized = str(value).strip().lower()
        if normalized == "standard":
            return None
        if normalized == "fast":
            return "fast"
        raise RuntimeError("Codex service tier must be standard or fast.")

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
        import math

        value = self.get("semantic_timeout_seconds")
        try:
            timeout = float(value) if value is not None else 600.0
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                "Provider timeout must be positive and finite."
            ) from error
        if isinstance(value, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise RuntimeError("Provider timeout must be positive and finite.")
        return timeout

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
