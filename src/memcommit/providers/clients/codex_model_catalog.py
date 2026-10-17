"""Read Codex's model/effort catalog without starting an inference thread."""

from __future__ import annotations

import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass

from memcommit.providers.clients.codex import CodexChatGPTProvider
from memcommit.providers.clients.completion import model_name
from memcommit.providers.errors import QueryProviderError, QueryProviderTimeoutError
from memcommit.providers.types import CODEX_REASONING_EFFORTS


@dataclass(frozen=True)
class CodexReasoningOption:
    effort: str
    description: str = ""


@dataclass(frozen=True)
class CodexModelOption:
    model: str
    display_name: str
    is_default: bool
    default_reasoning_effort: str | None
    supported_reasoning_efforts: tuple[CodexReasoningOption, ...]


def _decode_catalog_page(
    value: object,
) -> tuple[tuple[CodexModelOption, ...], str | None]:
    if not isinstance(value, dict) or not isinstance(value.get("data"), list):
        raise QueryProviderError("Codex returned an invalid model catalog.")
    models = []
    for item in value["data"]:
        if not isinstance(item, dict) or type(item.get("hidden", False)) is not bool:
            raise QueryProviderError("Codex returned an invalid model entry.")
        if item.get("hidden", False):
            continue
        model = model_name(item.get("model"))
        display_name = item.get("displayName")
        is_default = item.get("isDefault", False)
        efforts = item.get("supportedReasoningEfforts")
        default_effort = item.get("defaultReasoningEffort")
        if (
            not isinstance(display_name, str)
            or not display_name.strip()
            or "\n" in display_name
            or "\r" in display_name
            or type(is_default) is not bool
            or not isinstance(efforts, list)
        ):
            raise QueryProviderError("Codex returned invalid model selection metadata.")
        reasoning_options = []
        for effort in efforts:
            if (
                not isinstance(effort, dict)
                or effort.get("reasoningEffort") not in CODEX_REASONING_EFFORTS
                or not isinstance(effort.get("description", ""), str)
            ):
                raise QueryProviderError(
                    "Codex returned an unsupported reasoning option. Update memcommit and retry."
                )
            reasoning_options.append(
                CodexReasoningOption(
                    effort=effort["reasoningEffort"], description=effort.get("description", "")
                )
            )
        supported = tuple(option.effort for option in reasoning_options)
        if len(set(supported)) != len(supported) or (
            default_effort not in supported if supported else default_effort is not None
        ):
            raise QueryProviderError(
                "Codex returned an invalid default reasoning setting."
            )
        models.append(
            CodexModelOption(
                model=model,
                display_name=display_name,
                is_default=is_default,
                default_reasoning_effort=default_effort,
                supported_reasoning_efforts=tuple(reasoning_options),
            )
        )
    cursor = value.get("nextCursor")
    if cursor is not None and (
        not isinstance(cursor, str) or not cursor or len(cursor) > 1024
    ):
        raise QueryProviderError("Codex returned an invalid model catalog cursor.")
    return tuple(models), cursor


class _CodexCatalogSession:
    """One bounded stdio exchange; stdout buffering must not hide later replies."""

    def __init__(self, process: subprocess.Popen, timeout: float):
        self.process = process
        self.deadline = time.monotonic() + timeout
        self.buffer = b""
        self.bytes_received = 0
        self.request_id = 0
        os.set_blocking(process.stdin.fileno(), False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(process.stdout, selectors.EVENT_READ)

    def send(self, message: dict) -> None:
        pending = (json.dumps(message) + "\n").encode()
        try:
            with selectors.DefaultSelector() as writable:
                writable.register(self.process.stdin, selectors.EVENT_WRITE)
                while pending:
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0 or not writable.select(remaining):
                        raise QueryProviderTimeoutError(
                            "Codex model catalog timed out while sending a request."
                        )
                    try:
                        written = os.write(self.process.stdin.fileno(), pending)
                    except BlockingIOError:
                        continue
                    pending = pending[written:]
        except (BrokenPipeError, OSError) as error:
            raise QueryProviderError(
                "Codex model catalog connection closed. Update Codex or retry."
            ) from error

    def request(self, method: str, params: dict) -> object:
        self.request_id += 1
        request_id = self.request_id
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            while b"\n" in self.buffer:
                line, self.buffer = self.buffer.split(b"\n", 1)
                try:
                    message = json.loads(line)
                except (ValueError, UnicodeDecodeError) as error:
                    raise QueryProviderError(
                        "Codex returned an invalid catalog protocol response."
                    ) from error
                if not isinstance(message, dict):
                    raise QueryProviderError(
                        "Codex returned an invalid catalog protocol response."
                    )
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise QueryProviderError(
                        "Codex could not read the model catalog. Check login, update Codex, or retry."
                    )
                if "result" not in message:
                    raise QueryProviderError(
                        "Codex returned an incomplete catalog response."
                    )
                return message["result"]
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise QueryProviderTimeoutError(
                    "Codex model catalog timed out. Check the connection and retry."
                )
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                raise QueryProviderError(
                    "Codex model catalog connection closed. Update Codex or retry."
                )
            self.bytes_received += len(chunk)
            if self.bytes_received > 2_000_000:
                raise QueryProviderError(
                    "Codex model catalog exceeded its response limit."
                )
            self.buffer += chunk


def load_codex_model_catalog(
    provider: CodexChatGPTProvider, *, timeout: float = 30
) -> tuple[CodexModelOption, ...]:
    """Use the already authenticated CLI's picker-visible catalog, in server order."""
    if timeout <= 0:
        raise ValueError("Model catalog timeout must be positive.")
    with tempfile.TemporaryDirectory(prefix="memcommit-codex-catalog-") as directory:
        try:
            process = subprocess.Popen(
                args=[
                    str(provider.binary),
                    "app-server",
                    "--listen",
                    "stdio://",
                    "-c",
                    'model_provider="openai"',
                ],
                cwd=directory,
                env=provider.env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            raise QueryProviderError(
                "Could not start the Codex model catalog connection."
            ) from error
        session = _CodexCatalogSession(process=process, timeout=timeout)
        try:
            session.request(
                method="initialize", params={"clientInfo": {"name": "memcommit", "version": "0.0.1"}}
            )
            session.send({"method": "initialized", "params": {}})
            models = []
            cursor = None
            seen_cursors = set()
            # Model discovery never starts a thread or turn, so it cannot
            # disclose a Context or activate Codex's inference tools.
            for _page in range(20):
                params = {"limit": 100, "includeHidden": False}
                if cursor is not None:
                    params["cursor"] = cursor
                page_models, cursor = _decode_catalog_page(
                    session.request(method="model/list", params=params)
                )
                models.extend(page_models)
                if cursor is None:
                    break
                if cursor in seen_cursors:
                    raise QueryProviderError("Codex repeated a model catalog page.")
                seen_cursors.add(cursor)
            else:
                raise QueryProviderError("Codex model catalog exceeded its page limit.")
            if not models:
                raise QueryProviderError(
                    "Codex returned no visible models. Check login or retry."
                )
            if len({model.model for model in models}) != len(models):
                raise QueryProviderError("Codex returned duplicate model identifiers.")
            return tuple(models)
        finally:
            session.selector.close()
            try:
                process.stdin.close()
            except OSError:
                pass
            # A PATH executable may be a launcher with a child CLI. Close
            # only this isolated process group so timeout cannot orphan it.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=3)
            process.stdout.close()
