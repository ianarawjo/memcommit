"""Capture direct-Memory CLI owner resolution in real 180x52 color PTYs."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import textwrap

import pexpect


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
COLUMNS = 180
ROWS = 52

_BASE_PATH = (
    ROOT / "agent-records/docs/screenshots/mem-help-a-z-boundary-20260813/capture_help_a_z.py"
)
_SPEC = importlib.util.spec_from_file_location("memory_locator_capture_base", _BASE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
_BASE.OUT = OUT
_BASE.COLS = COLUMNS
_BASE.ROWS = ROWS

SOURCE_MEMORIES = (
    ("ca562047-0000-0000-0000-000000000001", "a is apple"),
    ("dbdb4436-0000-0000-0000-000000000002", "b is banana"),
    ("11111111-0000-0000-0000-000000000003", "c is cherry"),
    ("22222222-0000-0000-0000-000000000004", "d is date"),
)
DUPLICATE_UID = "aaaaaaaa-0000-0000-0000-000000000000"


def _environment(home: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "HOME": str(home),
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONPATH": str(ROOT / "src"),
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    return environment


def _prepare_store(home: Path, *, ambiguous: bool) -> None:
    script = textwrap.dedent(
        f"""
        from memcommit.context import Context, Memory
        from memcommit.persistence.store import MemoryStore

        store = MemoryStore()
        if {ambiguous!r}:
            source = Context(
                uid="30000000-0000-0000-0000-000000000003",
                name="practice/3",
            )
            target = Context(
                uid="40000000-0000-0000-0000-000000000004",
                name="practice/4",
            )
            source.add(Memory(uid={DUPLICATE_UID!r}, content="source duplicate"))
            target.add(Memory(uid={DUPLICATE_UID!r}, content="target duplicate"))
        else:
            source = Context(
                uid="30000000-0000-0000-0000-000000000003",
                name="practice/3",
            )
            target = Context(
                uid="40000000-0000-0000-0000-000000000004",
                name="practice/4",
            )
            for uid, content in {SOURCE_MEMORIES!r}:
                source.add(Memory(uid=uid, content=content))
        store.save(source)
        store.save(target)
        store.set_current(target.name)
        """
    )
    subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=_environment(home),
        check=True,
        capture_output=True,
        text=True,
    )


def _driver(body: str) -> str:
    prefix = textwrap.dedent(
        f"""
        import os
        import shlex
        import shutil
        import subprocess
        import sys
        import termios

        size = os.get_terminal_size()
        if (size.columns, size.lines) != ({COLUMNS}, {ROWS}):
            raise RuntimeError(f"Unexpected PTY size: {{size.columns}}x{{size.lines}}")
        attributes = termios.tcgetattr(sys.stdout.fileno())
        attributes[1] |= termios.OPOST | termios.ONLCR
        termios.tcsetattr(sys.stdout.fileno(), termios.TCSANOW, attributes)
        executable = shutil.which("mem")
        if executable is None:
            raise RuntimeError("mem executable is unavailable")

        def run(*arguments, expected=0):
            argv = [executable, *arguments]
            print("\\n$ " + shlex.join(["mem", *arguments]), flush=True)
            result = subprocess.run(argv)
            if result.returncode != expected:
                raise RuntimeError(
                    f"{{shlex.join(argv)}} returned {{result.returncode}}, "
                    f"expected {{expected}}"
                )
            return result

        print("LIVE COLOR PTY · 180 columns × 52 rows", flush=True)
        print("STORE · isolated disposable Profile", flush=True)
        """
    )
    return prefix + "\n" + textwrap.dedent(body).strip() + "\n"


def _capture(home: Path, stem: str, body: str) -> tuple[str, str]:
    recorder = _BASE._StreamRecorder()
    child = pexpect.spawn(
        sys.executable,
        ["-c", _driver(body)],
        cwd=str(ROOT),
        env=_environment(home),
        encoding="utf-8",
        codec_errors="replace",
        timeout=30,
        dimensions=(ROWS, COLUMNS),
    )
    child.logfile_read = recorder
    child.expect(pexpect.EOF, timeout=30)
    child.close()
    assert child.exitstatus == 0, (child.exitstatus, child.signalstatus)
    _BASE._snapshot(recorder, stem)
    raw = recorder.getvalue()
    plain = (OUT / f"{stem}.txt").read_text(encoding="utf-8")
    assert "LIVE COLOR PTY · 180 columns × 52 rows" in plain
    return raw, plain


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("*.png", "*.txt", "*.typescript"):
        for path in OUT.glob(suffix):
            path.unlink()

    with tempfile.TemporaryDirectory(prefix="mem-memory-locator-success-") as value:
        home = Path(value)
        _prepare_store(home, ambiguous=False)

        raw_01, plain_01 = _capture(
            home,
            "01-precondition-source-and-current-target",
            """
            run("pwd")
            run("list", "practice/3")
            run("list", "practice/4")
            print("\\nPRECONDITION · Source has 4 direct Memories · Target has 0 items")
            """,
        )
        raw_02, plain_02 = _capture(
            home,
            "02-bare-uid-embed-default-current-target",
            """
            run("embed", "ca562047")
            from memcommit.context import MemoryRef
            from memcommit.persistence.store import MemoryStore
            store = MemoryStore(create=False)
            target = store.load_direct("practice/4")
            item = next(iter(target.iter_items()))
            assert isinstance(item, MemoryRef) and item.is_live
            assert item.target_context_name == "practice/3"
            assert item.target_memory_uid == "ca562047-0000-0000-0000-000000000001"
            print("\\nVERIFIED · bare UID found practice/3 · omitted --into used practice/4")
            """,
        )
        raw_03, plain_03 = _capture(
            home,
            "03-bare-uid-reference-default-current-target",
            """
            run("reference", "dbdb4436")
            from memcommit.context import MemoryRef
            from memcommit.persistence.store import MemoryStore
            store = MemoryStore(create=False)
            target = store.load_direct("practice/4")
            matches = [
                item for item in target.iter_items()
                if isinstance(item, MemoryRef)
                and item.target_memory_uid == "dbdb4436-0000-0000-0000-000000000002"
            ]
            assert len(matches) == 1 and matches[0].is_snapshot
            print("\\nVERIFIED · Reference bare UID found practice/3 · Target is practice/4")
            """,
        )
        raw_04, plain_04 = _capture(
            home,
            "04-qualified-context-uid-embed",
            """
            run("embed", "practice/3:11111111")
            print("\\nVERIFIED · CONTEXT:UID selected the explicit direct owner")
            """,
        )
        raw_05, plain_05 = _capture(
            home,
            "05-relative-qualified-reference",
            """
            run("reference", "../3:22222222")
            print("\\nVERIFIED · relative owner resolved from practice/4 to practice/3")
            """,
        )
        raw_06, plain_06 = _capture(
            home,
            "06-read-only-target-verification",
            """
            run("list")
            from memcommit.context import MemoryRef
            from memcommit.persistence.store import MemoryStore
            store = MemoryStore(create=False)
            target = store.load_direct("practice/4")
            items = tuple(target.iter_items())
            assert len(items) == 4
            assert all(isinstance(item, MemoryRef) for item in items)
            assert sum(item.is_live for item in items) == 2
            assert sum(item.is_snapshot for item in items) == 2
            print("\\nREAD-ONLY VERIFIED · 2 live Embeds · 2 immutable References")
            """,
        )

    with tempfile.TemporaryDirectory(prefix="mem-memory-locator-ambiguous-") as value:
        home = Path(value)
        _prepare_store(home, ambiguous=True)
        raw_07, plain_07 = _capture(
            home,
            "07-duplicate-uid-blocked-with-all-owners",
            """
            from memcommit.persistence.store import MemoryStore, context_record_digest
            store = MemoryStore(create=False)
            before = context_record_digest(store.load_direct("practice/4"))
            checkpoints_before = len(store.list_checkpoints("practice/4"))
            run("embed", "aaaaaaaa", expected=1)
            store = MemoryStore(create=False)
            after = context_record_digest(store.load_direct("practice/4"))
            checkpoints_after = len(store.list_checkpoints("practice/4"))
            assert before == after
            assert checkpoints_before == checkpoints_after
            print("\\nBLOCKED · both owners displayed")
            print("TARGET RECORD UNCHANGED · YES")
            print("CHECKPOINT COUNT UNCHANGED · YES")
            """,
        )

    combined_raw = "".join(
        (raw_01, raw_02, raw_03, raw_04, raw_05, raw_06, raw_07)
    )
    combined_plain = "".join(
        (plain_01, plain_02, plain_03, plain_04, plain_05, plain_06, plain_07)
    )
    assert re.search(r"\x1b\[[0-9;]*32m", combined_raw)
    assert re.search(r"\x1b\[[0-9;]*31m", combined_raw)
    assert "Embedded Memory [ca562047] from 'practice/3'" in plain_02
    assert "Referenced snapshot [dbdb4436] from 'practice/3'" in plain_03
    assert "Embedded Memory [11111111] from 'practice/3'" in plain_04
    assert "Referenced snapshot [22222222] from 'practice/3'" in plain_05
    assert "Context: practice/4" in plain_06
    assert "2 live Embeds · 2 immutable References" in plain_06
    assert f'practice/3:{DUPLICATE_UID} "source duplicate"' in plain_07
    assert f'practice/4:{DUPLICATE_UID} "target duplicate"' in plain_07
    assert (
        "To select one, rerun with its CONTEXT:UID value shown above." in plain_07
    )
    assert "TARGET RECORD UNCHANGED · YES" in plain_07
    assert "CHECKPOINT COUNT UNCHANGED · YES" in plain_07
    assert "NO_COLOR" not in combined_plain


if __name__ == "__main__":
    main()
