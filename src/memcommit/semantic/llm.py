"""
    Lightweight LLM client. Defaults to the Ollama OpenAI-compatible endpoint.
    No third-party HTTP library required — uses stdlib urllib.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import warnings

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

    def __init__(
        self,
        model: str,
        base_url: str = OLLAMA_URL,
        timeout: int = 120,
        max_tokens: int = 4096,
        enforce_json: bool = True,
    ):
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.enforce_json = enforce_json

    def _post_chat(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            self.base_url,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())

    def chat(self, messages: list[dict]) -> str:
        """Send messages and return the assistant's reply text."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": self.max_tokens,
        }
        if self.enforce_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            result = self._post_chat(payload)
        except urllib.error.HTTPError as e:
            # Some OpenAI-compatible endpoints reject response_format.
            if self.enforce_json and e.code in (400, 422):
                try:
                    result = self._post_chat({
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "max_tokens": self.max_tokens,
                    })
                except urllib.error.HTTPError as retry_err:
                    detail = retry_err.read().decode("utf-8", errors="replace")
                    raise LLMError(
                        f"LLM endpoint returned HTTP {retry_err.code}: {detail[:400]}"
                    )
            else:
                detail = e.read().decode("utf-8", errors="replace")
                raise LLMError(f"LLM endpoint returned HTTP {e.code}: {detail[:400]}")
        except urllib.error.URLError as e:
            raise LLMError(
                f"Could not reach LLM endpoint at {self.base_url}: {e}\n"
                "Is Ollama running? (ollama serve)"
            )
        except json.JSONDecodeError as e:
            raise LLMError(f"Invalid JSON from LLM endpoint: {e}")

        try:
            choice = result["choices"][0]
            finish_reason = choice.get("finish_reason")
            if finish_reason == "length":
                warnings.warn(
                    "LLM output may be truncated (finish_reason=length). "
                    "Consider increasing max_tokens.",
                    RuntimeWarning,
                    stacklevel=2,
                )
            return choice["message"]["content"]
        except (KeyError, IndexError) as e:
            raise LLMError(f"Unexpected response shape from LLM: {e}\nGot: {result}")
