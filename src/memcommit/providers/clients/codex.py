"""One-shot Codex execution using the user's stored ChatGPT authentication."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from memcommit.providers.errors import QueryProviderError, QueryProviderTimeoutError
from memcommit.providers.types import (
    CODEX_CHATGPT_PROVIDER,
    CODEX_REASONING_EFFORTS,
    CompletionRun,
    ProviderIdentity,
)
from memcommit.providers.clients.completion import build_query_prompt
from memcommit.persistence.command_ledger.study_actions import (
    record_study_provider_turn,
)

API_BILLING_ENV = ("OPENAI_API_KEY", "CODEX_API_KEY")
AUTH_OVERRIDE_ENV = ("CODEX_ACCESS_TOKEN",)
_AUTH_ENV = (*API_BILLING_ENV, *AUTH_OVERRIDE_ENV)
_CODEX_MODEL_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]{0,255}\Z")


def _default_codex_candidates() -> list[Path]:
    """Return likely Codex executables without trusting a shell."""
    candidates = [
        Path("/Applications/ChatGPT.app/Contents/Resources/codex"),
    ]
    on_path = shutil.which("codex")
    if on_path:
        candidates.append(Path(on_path))
    candidates.append(Path.home() / ".local" / "bin" / "codex")

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    return unique


def _run_process(
    args: list[str],
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, **kwargs)  # type: ignore[arg-type]


def resolve_codex_binary(
    *,
    candidates: Iterable[Path] | None = None,
    env: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> Path:
    """Select the first candidate that identifies itself as the Codex CLI."""
    process_runner = runner or _run_process
    attempted: list[str] = []
    for candidate in candidates or _default_codex_candidates():
        attempted.append(str(candidate))
        try:
            result = process_runner(
                [str(candidate), "--version"],
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        output = f"{result.stdout}\n{result.stderr}"
        if result.returncode == 0 and any(
            line.strip().startswith("codex-cli ") for line in output.splitlines()
        ):
            return Path(os.path.abspath(candidate))

    paths = ", ".join(attempted) or "(none)"
    raise QueryProviderError("No working Codex CLI was found. Checked: " + paths)


@dataclass
class CodexChatGPTProvider:
    """One-shot Codex runner accepting only stored ChatGPT authentication."""

    binary: Path
    env: dict[str, str]
    timeout: float = 120
    model: str | None = None
    reasoning_effort: str | None = None
    service_tier: str | None = None
    identity: ProviderIdentity = field(init=False)
    last_run: CompletionRun | None = field(default=None, init=False)
    _runner: Callable[..., subprocess.CompletedProcess[str]] = field(
        default=_run_process,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.model is not None and _CODEX_MODEL_NAME.fullmatch(self.model) is None:
            raise QueryProviderError(
                "Codex model names must be 1-256 safe identifier characters."
            )
        if (
            self.reasoning_effort is not None
            and self.reasoning_effort not in CODEX_REASONING_EFFORTS
        ):
            raise QueryProviderError(
                "Unsupported Codex reasoning effort. Choose from: "
                + ", ".join(CODEX_REASONING_EFFORTS)
            )
        if self.service_tier not in {None, "fast"}:
            raise QueryProviderError(
                "Unsupported Codex service tier. Choose 'fast' or leave it unset."
            )
        self.identity = ProviderIdentity(
            provider=CODEX_CHATGPT_PROVIDER,
            model=self.model or "current-recommended",
            runtime=("codex-cli/fast" if self.service_tier == "fast" else "codex-cli"),
            reasoning_effort=self.reasoning_effort,
        )

    @classmethod
    def connect(
        cls,
        *,
        env: dict[str, str] | None = None,
        candidates: Iterable[Path] | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        timeout: float = 120,
        model: str | None = None,
        reasoning_effort: str | None = None,
        service_tier: str | None = None,
    ) -> CodexChatGPTProvider:
        """
        Verify that Codex will use a stored ChatGPT login, never an API key.

        The check intentionally fails closed if an environment-based
        authentication override is present.
        """
        process_runner = runner or _run_process
        original_env = dict(os.environ if env is None else env)
        overrides = [name for name in _AUTH_ENV if original_env.get(name)]
        if overrides:
            raise QueryProviderError(
                "Subscription-only query refused because authentication "
                f"override(s) are set: {', '.join(overrides)}. Unset them and "
                "use 'codex login' with ChatGPT."
            )

        child_env = original_env.copy()
        for name in _AUTH_ENV:
            child_env.pop(name, None)
        child_env["NO_COLOR"] = "1"
        child_env["RUST_LOG"] = "error"

        binary = resolve_codex_binary(
            candidates=candidates,
            env=child_env,
            runner=process_runner,
        )
        try:
            status = process_runner(
                [str(binary), "login", "status"],
                env=child_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            raise QueryProviderError("Could not verify the Codex login status.") from e

        status_lines = {
            line.strip() for line in f"{status.stdout}\n{status.stderr}".splitlines()
        }
        if status.returncode != 0 or "Logged in using ChatGPT" not in status_lines:
            raise QueryProviderError(
                "Subscription-backed mem commands require Codex to be logged "
                "in using ChatGPT. "
                "Run 'codex login' and choose ChatGPT; API-key login is not "
                "accepted by this research prototype."
            )

        return cls(
            binary=binary,
            env=child_env,
            timeout=timeout,
            model=model,
            reasoning_effort=reasoning_effort,
            service_tier=service_tier,
            _runner=process_runner,
        )

    @record_study_provider_turn
    def complete(
        self,
        prompt: str,
        *,
        operation: str,
        output_schema: dict[str, object] | None = None,
    ) -> str:
        """Run one isolated prompt and return only Codex's final message."""
        try:
            with tempfile.TemporaryDirectory(prefix="memcommit-codex-") as tmp:
                args = [
                    str(self.binary),
                    "exec",
                    "--ephemeral",
                    "--ignore-user-config",
                    "--ignore-rules",
                    "--skip-git-repo-check",
                    "--sandbox",
                    "read-only",
                    "--color",
                    "never",
                    "--cd",
                    tmp,
                    "--config",
                    'approval_policy="never"',
                    "--config",
                    'shell_environment_policy.inherit="none"',
                ]
                if self.model is not None:
                    args.extend(["--model", self.model])
                if self.reasoning_effort is not None:
                    args.extend(
                        [
                            "--config",
                            f'model_reasoning_effort="{self.reasoning_effort}"',
                        ]
                    )
                if self.service_tier == "fast":
                    # User config is deliberately ignored for isolation, so
                    # the Study condition must enable both documented Codex
                    # Fast-mode settings on every ephemeral invocation.
                    args.extend(
                        [
                            "--config",
                            'service_tier="fast"',
                            "--config",
                            "features.fast_mode=true",
                        ]
                    )
                if output_schema is not None:
                    schema_path = Path(tmp) / "output-schema.json"
                    with open(schema_path, "x", encoding="utf-8") as f:
                        json.dump(output_schema, f)
                    args.extend(["--output-schema", str(schema_path)])
                args.append("-")
                result = self._runner(
                    args,
                    input=prompt,
                    cwd=tmp,
                    env=self.env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired as e:
            raise QueryProviderTimeoutError(
                f"The temporary Codex {operation} timed out after "
                f"{self.timeout:g} seconds."
            ) from e
        except OSError as e:
            raise QueryProviderError(
                f"The temporary Codex {operation} could not be started."
            ) from e

        if result.returncode != 0:
            raise QueryProviderError(
                f"The temporary Codex {operation} failed (exit {result.returncode})."
            )
        answer = result.stdout.strip()
        if not answer:
            raise QueryProviderError(
                f"The temporary Codex {operation} returned no answer."
            )
        self.last_run = CompletionRun(
            identity=self.identity,
            operation=operation,
            upstream_model=self.model,
            upstream_provider="openai-codex",
        )
        return answer

    def query(self, source_name: str, source_content: str, question: str) -> str:
        if not question.strip():
            raise QueryProviderError("Question must be non-empty.")
        prompt = build_query_prompt(source_name, source_content, question)
        return self.complete(prompt, operation="query")
