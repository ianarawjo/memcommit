"""macOS Codex installation and provider-native ChatGPT login adapters."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from memcommit.application.operations.setup.application import setup_provider_option
from memcommit.providers.clients.codex import resolve_codex_binary


def find_provider_binary(provider_id: str) -> Path:
    setup_provider_option(provider_id)
    return resolve_codex_binary()


def provider_install_description(provider_id: str) -> str:
    setup_provider_option(provider_id)
    return "Run the official Codex installer: https://chatgpt.com/codex/install.sh"


def install_provider_runtime(provider_id: str) -> Path:
    setup_provider_option(provider_id)
    if sys.platform != "darwin":
        raise ValueError(
            "Automatic provider installation currently supports macOS only."
        )
    with tempfile.TemporaryDirectory(prefix="mem-provider-install-") as directory:
        script = Path(directory) / "install.sh"
        subprocess.run(
            [
                "/usr/bin/curl",
                "-fsSL",
                "--connect-timeout",
                "15",
                "--max-time",
                "60",
                "https://chatgpt.com/codex/install.sh",
                "-o",
                str(script),
            ],
            check=True,
        )
        environment = dict(os.environ, CODEX_NON_INTERACTIVE="1")
        subprocess.run(["/bin/sh", str(script)], env=environment, check=True)
    # Shell configuration affects the next terminal. The running setup must
    # also prefer the newly installed CLI over an older app-bundled fallback.
    install_dir = os.environ.get(
        "CODEX_INSTALL_DIR", str(Path.home() / ".local" / "bin")
    )
    os.environ["PATH"] = install_dir + os.pathsep + os.environ.get("PATH", "")
    return find_provider_binary(provider_id)


def login_provider(provider_id: str, binary: Path) -> None:
    setup_provider_option(provider_id)
    subprocess.run([str(binary), "login"], check=True)
