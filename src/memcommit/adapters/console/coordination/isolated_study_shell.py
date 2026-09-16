"""Keep interactive Study work inside a fresh, isolated zsh session.

Pilot-study feedback described recalling earlier commands with Up or shell
history search. Isolate that history when entering a Study, including the first
mem invocation after reopening a terminal. Reuse a matching Profile session;
initializing another Profile starts fresh history, never a saved shell.

This is terminal coordination, not Profile storage or a security sandbox.
The parent shell's history before the first mem invocation remains accessible.
"""

from __future__ import annotations

import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import (
    load_profile_registry,
    study_run_identity,
)

ISOLATED_STUDY_SHELL_ENV = "MEMCOMMIT_ISOLATED_STUDY_SHELL"
ISOLATED_STUDY_PROFILE_UID_ENV = "MEMCOMMIT_ISOLATED_STUDY_PROFILE_UID"
ISOLATED_STUDY_SESSION_ENV = "MEMCOMMIT_ISOLATED_STUDY_SESSION"
ISOLATED_STUDY_TOKEN_ENV = "MEMCOMMIT_ISOLATED_STUDY_TOKEN"
_SESSION_VARIABLES = (
    ISOLATED_STUDY_SHELL_ENV,
    ISOLATED_STUDY_PROFILE_UID_ENV,
    ISOLATED_STUDY_SESSION_ENV,
    ISOLATED_STUDY_TOKEN_ENV,
)
_CLI = (sys.executable, "-m", "memcommit.adapters.console.entrypoint")
_PENDING_TRANSITION_ERROR = (
    "An isolated Study shell transition is already pending; "
    "finish the current shell's jobs or exit before entering another command."
)
ShellRunner = Callable[..., subprocess.CompletedProcess[object]]


class IsolatedStudyShellError(RuntimeError):
    """An isolated Study shell could not be entered or coordinated."""


@dataclass(frozen=True)
class IsolatedStudyProfile:
    uid: str
    name: str


def _active_study_profile() -> IsolatedStudyProfile | None:
    profile = load_profile_registry().active
    if study_run_identity(profile) is None:
        return None
    return IsolatedStudyProfile(profile.uid, profile.name)


def _interactive_terminal() -> bool:
    return all(stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr))


def _write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=True)
    temporary.replace(path)


def _owned_session() -> tuple[Path, str] | None:
    """A stale environment marker must not stand in for a live session."""

    if os.environ.get(ISOLATED_STUDY_SHELL_ENV) != "1":
        return None
    try:
        root = Path(os.environ[ISOLATED_STUDY_SESSION_ENV])
        metadata = json.loads((root / "session.json").read_text(encoding="utf-8"))
        if (
            metadata["token"] != os.environ[ISOLATED_STUDY_TOKEN_ENV]
            or metadata["profile_uid"] != os.environ[ISOLATED_STUDY_PROFILE_UID_ENV]
        ):
            return None
        supervisor_pid = metadata["supervisor_pid"]
        if not isinstance(supervisor_pid, int) or supervisor_pid <= 0:
            return None
        os.kill(supervisor_pid, 0)
        return root, metadata["profile_uid"]
    except (OSError, KeyError, ValueError, TypeError):
        return None


def _request_transition(root: Path, command_argv: Sequence[str] | None) -> None:
    # Publish a complete request without replacing one whose command has yet
    # to run. Normal zsh job control can delay the owned shell's exit.
    with tempfile.NamedTemporaryFile(mode="w", dir=root, encoding="utf-8") as stream:
        json.dump({"argv": command_argv}, stream, ensure_ascii=True)
        stream.flush()
        try:
            os.link(stream.name, root / "request.json")
        except FileExistsError as error:
            raise IsolatedStudyShellError(_PENDING_TRANSITION_ERROR) from error


def ensure_isolated_study_shell(
    command_argv: Sequence[str] | None = None,
) -> int | None:
    """Keep, initialize, or leave an isolated Study shell at a CLI boundary.

    Before dispatch, argv is the unexecuted command (including an empty tuple
    for bare mem). After dispatch, None means it has already been executed.
    An integer means this invocation was handed off; None means continue.
    """

    if not _interactive_terminal():
        return None
    profile = _active_study_profile()
    session = _owned_session()
    if session is not None:
        root, profile_uid = session
        if (root / "request.json").exists():
            raise IsolatedStudyShellError(_PENDING_TRANSITION_ERROR)
        if profile is not None and profile.uid == profile_uid:
            return None
        # Only our own zsh observes this request at its next prompt and exits.
        # A mem child must never kill its parent or stack another shell in it.
        _request_transition(root, command_argv)
        return 0
    if profile is None:
        return None
    return run_isolated_study_shell(profile, command_argv=command_argv)


def _startup_text(root: Path, profile: IsolatedStudyProfile) -> str:
    prompt = (
        "isolated-study:" + display_escape_text(profile.name).replace("%", "%%") + "%# "
    )
    bootstrap = shlex.join(
        (
            sys.executable,
            "-m",
            "memcommit.adapters.console.coordination.isolated_study_shell",
            str(root),
        )
    )
    return (
        # This is the only rc file loaded, from a new private ZDOTDIR. The
        # global zshenv is still an unavoidable zsh startup boundary.
        "unsetopt SHARE_HISTORY APPEND_HISTORY INC_APPEND_HISTORY INC_APPEND_HISTORY_TIME PROMPT_SUBST\n"
        "HISTSIZE=1000\nSAVEHIST=0\n"
        f"HISTFILE={shlex.quote(str(root / 'history'))}\n"
        f"PROMPT={shlex.quote(prompt)}\n"
        "precmd() {\n"
        f"  [[ -f {shlex.quote(str(root / 'request.json'))} ]] && exit 0\n"
        "  return 0\n}\n"
        f"{bootstrap}\n"
    )


def run_isolated_study_shell(
    profile: IsolatedStudyProfile,
    *,
    command_argv: Sequence[str] | None = None,
    runner: ShellRunner = subprocess.run,
) -> int:
    """Run fresh isolated zsh sessions sequentially until Study work is left."""

    zsh_path = shutil.which("zsh")
    if zsh_path is None:
        raise IsolatedStudyShellError(
            "zsh was not found on PATH: mem requires zsh to start an isolated Study shell."
        )
    parent_environment = dict(os.environ)
    for variable in _SESSION_VARIABLES:
        parent_environment.pop(variable, None)
    pending = None if command_argv is None else list(command_argv)
    while True:
        with tempfile.TemporaryDirectory(
            prefix="memcommit-isolated-study-shell-"
        ) as directory:
            root = Path(directory)
            token = secrets.token_hex(24)
            _write_json(
                root / "session.json",
                {
                    "profile_uid": profile.uid,
                    "supervisor_pid": os.getpid(),
                    "token": token,
                },
            )
            _write_json(root / "pending.json", {"argv": pending})
            (root / ".zshrc").write_text(_startup_text(root, profile), encoding="utf-8")
            child_environment = dict(parent_environment)
            child_environment.update(
                {
                    ISOLATED_STUDY_SHELL_ENV: "1",
                    ISOLATED_STUDY_PROFILE_UID_ENV: profile.uid,
                    ISOLATED_STUDY_SESSION_ENV: str(root),
                    ISOLATED_STUDY_TOKEN_ENV: token,
                    "ZDOTDIR": str(root),
                    "HISTFILE": str(root / "history"),
                    "SAVEHIST": "0",
                }
            )
            typer.echo(
                "Initializing isolated Study shell for '"
                + display_escape_text(profile.name)
                + "' · fresh command history · exit returns to the previous shell.",
            )
            try:
                # -d skips global rc files; the private .zshrc supplies our
                # handoff hook. -f would also skip that owned startup file.
                result = runner(
                    (zsh_path, "-d", "-i"), check=False, env=child_environment
                )
            except KeyboardInterrupt:
                return 130
            except OSError as error:
                raise IsolatedStudyShellError(
                    f"Could not start the isolated Study shell: {error}"
                ) from error
            request = root / "request.json"
            if not request.exists():
                if (root / "pending.json").exists():
                    raise IsolatedStudyShellError(
                        "The isolated Study shell exited before its startup completed."
                    )
                typer.echo(f"Exited isolated Study shell · status {result.returncode}.")
                return int(result.returncode)
            pending = json.loads(request.read_text(encoding="utf-8"))["argv"]
        # Temporary history is discarded before another Profile is entered.
        profile = _active_study_profile()
        if profile is None:
            typer.echo("Exited isolated Study shell · returned to the regular shell.")
            if pending is not None:
                return int(
                    runner(
                        (*_CLI, *pending), check=False, env=parent_environment
                    ).returncode
                )
            return 0


def _bootstrap(root: Path) -> int:
    session = _owned_session()
    if session is None or session[0] != root:
        raise IsolatedStudyShellError(
            "The isolated Study shell session is no longer active."
        )
    pending = root / "pending.json"
    arguments = json.loads(pending.read_text(encoding="utf-8"))["argv"]
    pending.unlink()
    if arguments is None:
        return 0
    # argv never becomes shell source, so quotes, dollars and newlines remain
    # literal operands. Only this child owns the operation's attempt record.
    return subprocess.run((*_CLI, *arguments), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(_bootstrap(Path(sys.argv[1])))
