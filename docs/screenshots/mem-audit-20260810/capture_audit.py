"""Capture one real configured-provider Audit and its saved Review in a PTY."""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
import time
from collections.abc import Callable


ROWS = 52
COLUMNS = 180
TARGET = "task-3/local/results/additive-final"
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _drain(child, raw: bytearray, *, timeout: float = 0.1) -> bool:
    import pexpect

    try:
        raw.extend(child.read_nonblocking(size=65536, timeout=timeout))
        return True
    except (pexpect.TIMEOUT, pexpect.EOF):
        return False


def _wait_for(child, raw: bytearray, marker: bytes, *, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while marker not in raw:
        if not child.isalive():
            while _drain(child, raw, timeout=0.02):
                pass
            raise RuntimeError(
                f"Audit child exited before {marker!r}: "
                + raw[-4_000:].decode("utf-8", errors="replace")
            )
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for {marker!r}.")
        _drain(child, raw)
    time.sleep(0.25)
    while _drain(child, raw, timeout=0.02):
        pass


def _plain_screen(raw: bytes) -> str:
    import pyte

    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))
    return "\n".join(screen.display)


def _wait_for_screen(
    child,
    raw: bytearray,
    predicate: Callable[[str], bool],
    *,
    label: str,
    timeout: float,
) -> str:
    """Wait on the rendered terminal canvas, not ANSI-split raw text."""

    deadline = time.monotonic() + timeout
    while True:
        _drain(child, raw)
        plain = _plain_screen(bytes(raw))
        if predicate(plain):
            time.sleep(0.25)
            while _drain(child, raw, timeout=0.02):
                pass
            return _plain_screen(bytes(raw))
        if not child.isalive():
            while _drain(child, raw, timeout=0.02):
                pass
            raise RuntimeError(
                f"Audit child exited before {label}: "
                + _plain_screen(bytes(raw))[-4_000:]
            )
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Timed out waiting for rendered {label}.")


def _wait_for_exit(child, raw: bytearray, *, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while child.isalive() and time.monotonic() < deadline:
        _drain(child, raw)
    while _drain(child, raw, timeout=0.02):
        pass
    child.close()
    if child.isalive():
        raise RuntimeError("Audit child did not exit.")
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Audit child exited with {child.exitstatus}.")


def _ansi_color(value: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    colors = {
        "black": (30, 32, 48),
        "red": (237, 135, 150),
        "green": (166, 218, 149),
        "brown": (238, 212, 159),
        "blue": (138, 173, 244),
        "magenta": (198, 160, 246),
        "cyan": (139, 213, 255),
        "white": (244, 245, 247),
        "brightblack": (91, 96, 120),
        "brightred": (237, 135, 150),
        "brightgreen": (166, 218, 149),
        "brightbrown": (238, 212, 159),
        "brightblue": (138, 173, 244),
        "brightmagenta": (198, 160, 246),
        "brightcyan": (145, 215, 227),
        "brightwhite": (255, 255, 255),
        "default": default,
    }
    if value in colors:
        return colors[value]
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    return default


def _render_snapshot(name: str, raw: bytes) -> str:
    import pyte
    from PIL import Image, ImageDraw, ImageFont

    screen = pyte.Screen(COLUMNS, ROWS)
    stream = pyte.Stream(screen)
    stream.feed(raw.decode("utf-8", errors="replace"))
    plain = "\n".join(screen.display)
    (CAPTURE_DIR / f"{name}.txt").write_text(plain + "\n", encoding="utf-8")
    (CAPTURE_DIR / f"{name}.typescript").write_bytes(raw)

    font = ImageFont.truetype(
        "/opt/anaconda3/lib/python3.12/site-packages/matplotlib/"
        "mpl-data/fonts/ttf/DejaVuSansMono.ttf",
        18,
    )
    cell_width = 11
    cell_height = 21
    background = (30, 32, 48)
    foreground = (244, 245, 247)
    image = Image.new(
        "RGB",
        (COLUMNS * cell_width, ROWS * cell_height),
        background,
    )
    draw = ImageDraw.Draw(image)
    for row in range(ROWS):
        for column in range(COLUMNS):
            character = screen.buffer[row][column]
            fg = _ansi_color(character.fg, foreground)
            bg = _ansi_color(character.bg, background)
            if character.reverse:
                fg, bg = bg, fg
            x = column * cell_width
            y = row * cell_height
            if bg != background:
                draw.rectangle(
                    (x, y, x + cell_width - 1, y + cell_height - 1),
                    fill=bg,
                )
            if character.data != " ":
                draw.text((x, y - 1), character.data, font=font, fill=fg)
                if character.bold:
                    draw.text((x + 1, y - 1), character.data, font=font, fill=fg)
    image.save(CAPTURE_DIR / f"{name}.png")
    return plain


def _spawn(environment: dict[str, str], *arguments: str):
    import pexpect

    return pexpect.spawn(
        sys.executable,
        ["-m", "memcommit.cli", *arguments],
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )


def _new_audit_uid(before: set[str]) -> str:
    from memcommit.quality_audit_store import QualityAuditStore
    from memcommit.store import MemoryStore

    sessions = [
        session
        for session in QualityAuditStore(MemoryStore()).list()
        if session.uid not in before and session.source.context_name == TARGET
    ]
    if len(sessions) != 1:
        raise RuntimeError(
            f"Expected one newly saved Audit for {TARGET!r}; found {len(sessions)}."
        )
    return sessions[0].uid


def main() -> None:
    from memcommit.quality_audit import quality_audit_resolution_view
    from memcommit.quality_audit_store import QualityAuditStore
    from memcommit.store import MemoryStore

    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    print(f"CAPTURE PTY · {COLUMNS} columns × {ROWS} rows", flush=True)
    print(f"TARGET · {TARGET}", flush=True)
    existing = {session.uid for session in QualityAuditStore(MemoryStore()).list()}

    setup_raw = bytearray()
    setup = _spawn(environment, "audit")
    _wait_for(setup, setup_raw, b"RUN AUDIT", timeout=10)
    setup_plain = _render_snapshot("01-audit-setup", bytes(setup_raw))
    if "ALL READABLE CONTEXTS" not in setup_plain or "RUN AUDIT" not in setup_plain:
        raise RuntimeError("Audit setup capture omitted its required controls.")
    setup.send(b"\x1b")
    _wait_for_exit(setup, setup_raw)

    audit_raw = bytearray()
    audit = _spawn(environment, "audit", "--context", TARGET)
    _wait_for_screen(
        audit,
        audit_raw,
        lambda plain: all(
            marker in plain
            for marker in (
                "1. DUPLICATES   · COMPLETE",
                "2. AMBIGUITIES  · COMPLETE",
                "3. CONFLICTS    · RUNNING",
            )
        ),
        label="cumulative Conflict stage",
        timeout=1_800,
    )
    sequence_plain = _render_snapshot(
        "02-audit-checks-sequence",
        bytes(audit_raw),
    )
    if not all(
        marker in sequence_plain
        for marker in (
            "1. DUPLICATES   · COMPLETE",
            "2. AMBIGUITIES  · COMPLETE",
            "3. CONFLICTS    · RUNNING",
        )
    ):
        raise RuntimeError("Audit wait capture did not preserve cumulative stages.")

    audit.send(b"h")
    _wait_for_screen(
        audit,
        audit_raw,
        lambda plain: (
            "mem help · explore while work continues" in plain
            and "MEM AUDIT" in plain
        ),
        label="Help during Audit",
        timeout=10,
    )
    help_plain = _render_snapshot("03-help-during-audit", bytes(audit_raw))
    if "MEM AUDIT" not in help_plain or "H hide Help" not in help_plain:
        raise RuntimeError("Audit Help did not retain the running operation status.")

    audit.send(b"h")
    time.sleep(0.75)
    while _drain(audit, audit_raw, timeout=0.02):
        pass
    restored_plain = _render_snapshot(
        "04-audit-checks-restored",
        bytes(audit_raw),
    )
    if "AUDIT CHECKS · 1 → 2 → 3" not in restored_plain:
        raise RuntimeError("Closing Help did not restore the cumulative Audit view.")

    _wait_for_screen(
        audit,
        audit_raw,
        lambda plain: (
            "AUDIT SUMMARY" in plain and "SAVED · 3/3 CHECKS" in plain
        ),
        label="completed Audit report",
        timeout=900,
    )
    report_plain = _render_snapshot("05-complete-audit-report", bytes(audit_raw))
    if not all(
        marker in report_plain
        for marker in ("DUPLICATES", "AMBIGUITIES", "CONFLICTS", "COMPLETE")
    ):
        raise RuntimeError("Complete Audit report omitted a finder section.")

    audit_uid = _new_audit_uid(existing)
    saved = QualityAuditStore(MemoryStore()).load(audit_uid)
    view = quality_audit_resolution_view(saved)
    print(f"AUDIT UID · {audit_uid}", flush=True)
    print(
        "RESULTS · "
        + " · ".join(
            f"{check.kind.upper()} {len(check.report.findings)}"
            for check in saved.checks
        ),
        flush=True,
    )

    if view.items:
        # Viewer → Items. Enter opens the checked item and returns focus to
        # Viewer; subsequent opened details add Responses before Items.
        audit.send(b"\t\x1b[B\r")
        time.sleep(0.5)
        while _drain(audit, audit_raw, timeout=0.02):
            pass
        for index, item in enumerate(view.items, start=1):
            if index > 1:
                audit.send(b"\t\t\x1b[B\r")
                time.sleep(0.5)
                while _drain(audit, audit_raw, timeout=0.02):
                    pass
            detail_plain = _render_snapshot(
                f"{5 + index:02d}-review-{item.kind.casefold()}-{index}",
                bytes(audit_raw),
            )
            if item.kind not in detail_plain:
                raise RuntimeError(
                    f"Audit item capture {index} did not show {item.kind}."
                )

    audit.send(b"\x1b")
    time.sleep(0.3)
    while _drain(audit, audit_raw, timeout=0.02):
        pass
    audit.send(b"\x1b")
    _wait_for_exit(audit, audit_raw, timeout=15)
    _render_snapshot("20-audit-saved-receipt", bytes(audit_raw))

    review_raw = bytearray()
    review = _spawn(environment, "review", "audit", "--session", audit_uid)
    _wait_for_screen(
        review,
        review_raw,
        lambda plain: (
            "AUDIT SUMMARY" in plain and "SAVED · 3/3 CHECKS" in plain
        ),
        label="saved Audit Review",
        timeout=10,
    )
    reopened_plain = _render_snapshot("21-saved-review-reopened", bytes(review_raw))
    if TARGET not in reopened_plain or "SAVED · 3/3 CHECKS" not in reopened_plain:
        raise RuntimeError("Saved Audit Review did not reopen the exact UID.")
    review.send(b"\x1b")
    _wait_for_exit(review, review_raw)

    snapshot_raw = bytearray()
    snapshot = _spawn(
        environment,
        "review",
        "audit",
        "--session",
        audit_uid,
        "--snapshot",
    )
    _wait_for_exit(snapshot, snapshot_raw)
    snapshot_plain = _render_snapshot("22-saved-review-snapshot", bytes(snapshot_raw))
    if "3/3 CHECKS" not in snapshot_plain:
        raise RuntimeError("Saved Review snapshot omitted completion status.")

    combined = bytes(setup_raw + audit_raw + review_raw + snapshot_raw)
    if b"\x1b[" not in combined:
        raise RuntimeError("PTY stream did not contain ANSI controls.")
    if b"38;2;" not in combined and b"38;5;" not in combined:
        raise RuntimeError("PTY stream did not contain foreground color styles.")
    print("CAPTURE VERIFIED · ANSI COLOR PRESENT · SOURCE UNCHANGED", flush=True)


if __name__ == "__main__":
    main()
