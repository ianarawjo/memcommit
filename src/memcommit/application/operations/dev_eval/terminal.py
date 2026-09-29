"""Run authored CLI arguments in a PTY and retain their actual output."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import struct
import subprocess
import sys
import termios
from dataclasses import dataclass

import memcommit
from memcommit.application.operations.profile.config import resolve_active_store_dir
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class TerminalResult:
    arguments: tuple[str, ...]
    output: str
    returncode: int


class ScenarioTerminal:
    """One 180×52 terminal for sequential commands in the current Profile."""

    def __init__(self, store: MemoryStore):
        self.store = store
        self.results: list[TerminalResult] = []
        self._master: int | None = None
        self._slave: int | None = None

    def __enter__(self) -> ScenarioTerminal:
        self._master, self._slave = pty.openpty()
        fcntl.ioctl(self._slave, termios.TIOCSWINSZ, struct.pack("HHHH", 52, 180, 0, 0))
        return self

    def __exit__(self, *exc) -> None:
        for descriptor in (self._master, self._slave):
            if descriptor is not None:
                os.close(descriptor)
        self._master = self._slave = None

    def run(self, *arguments: str) -> TerminalResult:
        if self._master is None or self._slave is None:
            raise RuntimeError("Open the scenario terminal before running a command.")
        if resolve_active_store_dir().resolve() != self.store.store_dir.resolve():
            raise RuntimeError(
                "The active Profile no longer matches this scenario's Store."
            )
        environment = dict(os.environ)
        environment.pop("NO_COLOR", None)
        environment.update(TERM="xterm-256color", COLORTERM="truecolor")
        # A PATH-installed mem may still point at another checkout. Exercise the
        # real CLI entrypoint from the same package/interpreter as this scenario.
        source_root = str(Path(memcommit.__file__).resolve().parent.parent)
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, (source_root, environment.get("PYTHONPATH")))
        )
        process = subprocess.Popen(
            (sys.executable, "-m", "memcommit.adapters.console.entrypoint", *arguments),
            stdin=self._slave,
            stdout=self._slave,
            stderr=self._slave,
            env=environment,
            start_new_session=True,
        )
        output = bytearray()
        try:
            while process.poll() is None:
                # Polling observes process exit; it does not limit command duration.
                if select.select([self._master], [], [], 0.05)[0]:
                    output.extend(os.read(self._master, 65536))
        finally:
            # Cancellation/read failure must not leave a command running in the background.
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()
        while select.select([self._master], [], [], 0)[0]:
            output.extend(os.read(self._master, 65536))
        result = TerminalResult(
            arguments,
            output.decode("utf-8", errors="replace"),
            process.returncode,
        )
        self.results.append(result)
        return result
