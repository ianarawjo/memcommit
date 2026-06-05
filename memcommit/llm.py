"""
    Lightweight LLM client. Defaults to the Ollama OpenAI-compatible endpoint.
    No third-party HTTP library required — uses stdlib urllib.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/v1/chat/completions"


class LLMError(Exception):
    pass


class LLMClient:
    """
    Sends chat completion requests to an OpenAI-compatible endpoint.

    model examples:
      "llama3.2"          → Ollama (default base URL)
      "mistral"           → Ollama
    """

    def __init__(self, model: str, base_url: str = OLLAMA_URL, timeout: int = 120):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout

    def chat(self, messages: list[dict]) -> str:
        """Send messages and return the assistant's reply text."""
        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "stream": False,
        }).encode()
        req = urllib.request.Request(
            self.base_url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
        except urllib.error.URLError as e:
            raise LLMError(
                f"Could not reach LLM endpoint at {self.base_url}: {e}\n"
                "Is Ollama running? (ollama serve)"
            )
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from LLM endpoint: {e}")

        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected response shape from LLM: {e}\nGot: {result}")
