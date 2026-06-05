"""Global configuration for mem (~/.mem/config.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

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
