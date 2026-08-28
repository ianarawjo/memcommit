"""Capture the optional fourth Audit check through the real shared TUI shells."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


ROWS = 52
COLUMNS = 180
CAPTURE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _demo_child() -> None:
    """Run the product Audit wait/review path with deterministic provider replies."""

    from memcommit.application import ops
    from memcommit.adapters.console.commands.audit.command import (
        _run_quality_audit_checks,
        run_quality_audit_review,
    )
    from memcommit.application.operations.conformance.model import CONTEXT_CONFORMANCE_OPERATION
    from memcommit.providers.types import ProviderIdentity
    from memcommit.application.reviewing.quality.audit import quality_audit_resolution_view
    from memcommit.application.reviewing.quality.audit_store import QualityAuditStore
    from memcommit.adapters.console.shared.resolution_workbench_shell import (
        render_resolution_workbench_snapshot,
    )
    from memcommit.application.operations.review.model import direct_context_digest
    from memcommit.persistence.store import MemoryStore

    terminal_size = os.get_terminal_size(sys.stdout.fileno())
    if (terminal_size.lines, terminal_size.columns) != (ROWS, COLUMNS):
        raise RuntimeError(
            f"Expected a {COLUMNS}x{ROWS} PTY; got "
            f"{terminal_size.columns}x{terminal_size.lines}."
        )

    class DemoProvider:
        identity = ProviderIdentity(
            provider="capture",
            model="deterministic-audit-conformance",
        )

        def complete(self, prompt, *, operation, output_schema=None):
            del prompt, output_schema
            if operation.startswith("find_"):
                time.sleep(0.35)
                return '{"findings": []}'
            if operation != CONTEXT_CONFORMANCE_OPERATION:
                raise RuntimeError(f"Unexpected operation: {operation}")
            # Keep the fourth row visible long enough for a real PTY capture.
            time.sleep(2.0)
            return json.dumps(
                {
                    "overview": "Both examples follow the frozen initialism Rule.",
                    "judgments": [
                        {
                            "rule_id": "r1",
                            "status": "CONFORMS",
                            "evidence_memory_ids": ["m000001", "m000002"],
                            "reason": "Each output uses the initials of its input name.",
                        }
                    ],
                    "outside_memory_ids": [],
                }
            )

    target = ops.init("ticker/examples")
    ops.add(target, "North Star Energy -> NSE")
    ops.add(target, "Blue River Holdings -> BRH")
    rules = ops.init("ticker/rules")
    ops.add(rules, "Use uppercase initials for multiword names.")

    with tempfile.TemporaryDirectory(prefix="mem-audit-conformance-") as directory:
        store = MemoryStore(root=Path(directory) / ".mem")
        store.create_context(target)
        store.create_context(rules)
        target_before = direct_context_digest(store.load_direct(target.name))
        rules_before = direct_context_digest(store.load_direct(rules.name))

        session = _run_quality_audit_checks(
            target,
            DemoProvider,
            conformance_rules=rules,
            interactive=True,
            interval=0.08,
        )
        QualityAuditStore(store).save(session, expected_digest=None)
        run_quality_audit_review(store, session)

        restored = QualityAuditStore(store).load(session.uid)
        target_after = direct_context_digest(store.load_direct(target.name))
        rules_after = direct_context_digest(store.load_direct(rules.name))
        unchanged = target_before == target_after and rules_before == rules_after
        no_checkpoints = (
            not store.list_checkpoints(target.name)
            and not store.list_checkpoints(rules.name)
        )
        print("\nREAD-ONLY VERIFICATION", flush=True)
        print(
            render_resolution_workbench_snapshot(
                quality_audit_resolution_view(restored)
            ),
            flush=True,
        )
        print(
            "SOURCE AND RULES UNCHANGED · "
            + ("YES" if unchanged else "NO"),
            flush=True,
        )
        print(
            "CHECKPOINTS CREATED · " + ("NO" if no_checkpoints else "YES"),
            flush=True,
        )
        print(f"SAVED AUDIT UID · {restored.uid}", flush=True)
        if not unchanged or not no_checkpoints or restored.conformance is None:
            raise RuntimeError("Audit capture violated its read-only boundary.")


def _drain(child, raw: bytearray, *, timeout: float = 0.1) -> None:
    import pexpect

    try:
        raw.extend(child.read_nonblocking(size=65536, timeout=timeout))
    except (pexpect.TIMEOUT, pexpect.EOF):
        pass


def _plain_screen(raw: bytes) -> str:
    import pyte

    screen = pyte.Screen(COLUMNS, ROWS)
    pyte.Stream(screen).feed(raw.decode("utf-8", errors="replace"))
    return "\n".join(screen.display)


def _wait_for_screen(child, raw: bytearray, markers: tuple[str, ...], timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _drain(child, raw)
        plain = _plain_screen(bytes(raw))
        if all(marker in plain for marker in markers):
            time.sleep(0.2)
            _drain(child, raw, timeout=0.02)
            return
        if not child.isalive():
            raise RuntimeError(
                "Capture child exited early:\n" + _plain_screen(bytes(raw))
            )
    raise RuntimeError("Timed out waiting for " + repr(markers))


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
    pyte.Stream(screen).feed(raw.decode("utf-8", errors="replace"))
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
    image = Image.new("RGB", (COLUMNS * cell_width, ROWS * cell_height), background)
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


def _capture_parent() -> None:
    import pexpect

    environment = dict(os.environ)
    environment.pop("NO_COLOR", None)
    environment.update(
        {
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG": "1",
        }
    )
    child = pexpect.spawn(
        sys.executable,
        [str(Path(__file__).resolve()), "--child"],
        cwd=str(REPOSITORY_ROOT),
        env=environment,
        dimensions=(ROWS, COLUMNS),
        encoding=None,
        timeout=0.1,
    )
    raw = bytearray()
    _wait_for_screen(
        child,
        raw,
        (
            "AUDIT CHECKS · 1 → 2 → 3 → 4",
            "3. CONFLICTS    · COMPLETE",
            "4. CONFORMANCE  · RUNNING",
        ),
        20,
    )
    wait_plain = _render_snapshot("01-fourth-check-running", bytes(raw))
    if "RULE CONFORMANCE" not in wait_plain:
        raise RuntimeError("The four-check wait view omitted its rule boundary.")

    _wait_for_screen(
        child,
        raw,
        ("AUDIT SUMMARY", "SAVED · 4/4 CHECKS", "CONFORMANCE · COMPLETE"),
        20,
    )
    report_plain = _render_snapshot("02-complete-four-check-audit", bytes(raw))
    if "CONFORMANCE ISSUES" not in report_plain:
        raise RuntimeError("The saved Audit overview omitted Conformance.")

    child.send(b"\x1b")
    _wait_for_screen(
        child,
        raw,
        (
            "READ-ONLY VERIFICATION",
            "SOURCE AND RULES UNCHANGED · YES",
            "CHECKPOINTS CREATED · NO",
        ),
        15,
    )
    _render_snapshot("03-read-only-verification", bytes(raw))
    while child.isalive():
        _drain(child, raw, timeout=0.1)
    child.close()
    if child.exitstatus not in {0, None}:
        raise RuntimeError(f"Capture child exited with {child.exitstatus}.")
    if b"\x1b[" not in raw or (b"38;2;" not in raw and b"38;5;" not in raw):
        raise RuntimeError("Capture did not preserve ANSI foreground color.")
    print("CAPTURE VERIFIED · 180x52 · ANSI COLOR · READ-ONLY", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["--child"]:
        _demo_child()
    else:
        _capture_parent()
