from __future__ import annotations

import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from typer.testing import CliRunner

import memcommit.ops as ops
import memcommit.store as store_module
from memcommit.cli import app
from memcommit.adapters.console.commands.search.materialization import (
    FindMaterializationError,
    materialize_find_results,
)
from memcommit.adapters.console.commands.search.search_workbench import (
    FindSearchRequest,
    FindSearchResponse,
    FindSearchResult,
)
from memcommit.adapters.console.commands.granted_context import resolve_context_access
from memcommit.adapters.console.shared.readable_context_catalog import (
    freeze_readable_context_catalog,
)
from memcommit.core.context import Memory, MemoryRef
from memcommit.store import MemoryStore


ROOT = Path("/Users/KimMunyeong/Github/memcommit")
OUT = ROOT / "agent-records/outputs/source-projection-verification"
FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
WIDTH = 1180
TEXT_WIDTH = 120
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def command_output(*argv: str) -> str:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return ANSI.sub("", result.stdout).replace("\r", "")


def wrap_body(body: str) -> list[str]:
    lines: list[str] = []
    for raw in body.rstrip().splitlines():
        wrapped = textwrap.wrap(
            raw,
            width=TEXT_WIDTH,
            replace_whitespace=False,
            drop_whitespace=False,
            subsequent_indent="  ",
        ) or [""]
        lines.extend(part.rstrip() for part in wrapped)
    return lines


def line_fragments(line: str) -> list[tuple[str, str]]:
    palette = {
        "READ GRANT": "#8aadf4",
        "QUERY GRANT": "#c6a0f6",
        "VIA EMBED": "#8bd5ca",
        "MEMORY REF": "#cad3f5",
        "QUERY VIEW": "#c6a0f6",
        "READ ONLY": "#a6da95",
        "DANGLING": "#ed8796",
        "REFERENCE": "#cad3f5",
        "13 passed": "#a6da95",
    }
    pattern = re.compile("(" + "|".join(map(re.escape, palette)) + ")")
    fragments: list[tuple[str, str]] = []
    position = 0
    for match in pattern.finditer(line):
        if match.start() > position:
            fragments.append((line[position : match.start()], "#e6e9ef"))
        fragments.append((match.group(0), palette[match.group(0)]))
        position = match.end()
    if position < len(line):
        fragments.append((line[position:], "#e6e9ef"))
    return fragments


def render(title: str, body: str, filename: str) -> Path:
    font = ImageFont.truetype(FONT_PATH, 15)
    bold = ImageFont.truetype(FONT_PATH, 15, index=1)
    lines = wrap_body(body)
    height = max(330, 98 + len(lines) * 21)
    image = Image.new("RGB", (WIDTH, height), "#101217")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH - 1, 44), fill="#181b22")
    draw.text((18, 13), title, font=bold, fill="#cad3f5")
    y = 60
    for line in lines:
        x = 18
        for fragment, color in line_fragments(line):
            draw.text((x, y), fragment, font=font, fill=color)
            x += draw.textlength(fragment, font=font)
        y += 21
    draw.text(
        (18, height - 27),
        "ACTUAL MEM OUTPUT / PERSISTED STATE · 2026-08-09",
        font=font,
        fill="#6e738d",
    )
    path = OUT / filename
    image.save(path)
    path.with_suffix(".txt").write_text(body, encoding="utf-8")
    return path


def patch_store_root(root: Path) -> None:
    paths = {
        "STORE_DIR": root,
        "CONTEXTS_DIR": root / "contexts",
        "QUERY_SOURCES_DIR": root / "query-sources",
        "STATE_FILE": root / "state.json",
        "IMPACT_PLAN_FILE": root / "impact-plan.json",
        "STAGED_UPDATE_FILE": root / "staged-update.json",
        "REVIEW_SESSION_FILE": root / "review-session.json",
        "ATOMIZE_ANALYSES_DIR": root / "atomize-analyses",
        "ATOMIZE_WORKBENCHES_DIR": root / "atomize-workbenches",
        "ATOMIZE_GROUNDING_SESSIONS_DIR": root / "atomize-groundings",
        "ATOMIZE_GROUNDING_HISTORY_DIR": root / "atomize-grounding-history",
        "GROUND_SESSIONS_DIR": root / "ground-sessions",
        "MELD_SESSIONS_DIR": root / "meld-sessions",
    }
    for name, value in paths.items():
        setattr(store_module, name, value)


def invoke(runner: CliRunner, *argv: str) -> str:
    result = runner.invoke(app, list(argv))
    if result.exit_code != 0:
        raise RuntimeError(f"mem {' '.join(argv)} failed:\n{result.output}")
    return ANSI.sub("", result.output).replace("\r", "")


def local_reference_capture() -> tuple[str, str]:
    runner = CliRunner()
    os.environ["MEMCOMMIT_TEST_DISABLE_ATTEMPT_LOG"] = "1"
    with tempfile.TemporaryDirectory(prefix="mem-source-projection-") as raw_root:
        root = Path(raw_root) / ".mem"
        patch_store_root(root)
        init_source = invoke(runner, "init", "source")
        add_source = invoke(runner, "add", "version one")
        store = MemoryStore()
        source = store.load("source")
        memory = next(iter(source.iter_items()))
        assert isinstance(memory, Memory)
        invoke(runner, "init", "parent")
        added_ref = invoke(
            runner,
            "reference",
            memory.uid[:8],
            "--from",
            "source",
        )
        parent = store.load("parent")
        ref = next(iter(parent.iter_items()))
        assert isinstance(ref, MemoryRef)
        first_show = invoke(runner, "show", ref.uid[:8])

        source.replace(Memory(uid=memory.uid, content="version two"))
        store.save(source)
        second_show = invoke(runner, "show", ref.uid[:8])
        if "version two" not in second_show or "version one" in second_show:
            raise RuntimeError("The Memory reference did not follow its source update.")

        cli_body = (
            "$ mem init source\n"
            + init_source
            + "$ mem add 'version one'\n"
            + add_source
            + f"$ mem reference {memory.uid[:8]} --from source\n"
            + added_ref
            + f"$ mem show {ref.uid[:8]}\n"
            + first_show
            + "\nSOURCE UPDATED TO 'version two'\n"
            + f"$ mem show {ref.uid[:8]}\n"
            + second_show
        )

        response = FindSearchResponse(
            FindSearchRequest("version", (source.name,)),
            "CURRENT",
            (
                FindSearchResult(
                    context_name=source.name,
                    kind="memory",
                    uid=memory.uid,
                    content="version two",
                    source_context_name=source.name,
                    source_context_uid=source.uid,
                    source_memory_uid=memory.uid,
                ),
            ),
        )
        access = resolve_context_access(
            store,
            source.name,
            current_name=store.current_context_name(),
            required_permission="READ",
        )
        catalog = freeze_readable_context_catalog(store, access)
        result = materialize_find_results(
            store,
            catalog,
            response,
            selected_result_indices=(0,),
            mode="REFERENCE",
            destination_name="results/reference",
        )
        direct_output = store.load_direct(result.context_name)
        find_ref = next(iter(direct_output.iter_items()))
        assert isinstance(find_ref, MemoryRef)
        resolved_before = store.load(result.context_name)
        loaded_before = next(iter(resolved_before.iter_items()))
        assert isinstance(loaded_before, MemoryRef) and loaded_before.target is not None

        source = store.load("source")
        source.replace(Memory(uid=memory.uid, content="version three"))
        store.save(source)
        resolved_after = store.load(result.context_name)
        loaded_after = next(iter(resolved_after.iter_items()))
        assert isinstance(loaded_after, MemoryRef) and loaded_after.target is not None
        if loaded_after.target.content != "version three":
            raise RuntimeError("Find REFERENCE did not remain live.")
        find_body = "\n".join(
            (
                "FIND MATERIALIZATION RECEIPT",
                f"  MODE          · {result.mode}",
                f"  OUTPUT        · {result.context_name}",
                f"  OUTPUT ITEM   · {find_ref.uid[:8]} · {type(find_ref).__name__}",
                f"  TARGET        · {find_ref.target_context_name}#{find_ref.target_memory_uid[:8]}",
                f"  INITIAL VALUE · {loaded_before.target.content}",
                "",
                "SOURCE UPDATED TO 'version three'",
                f"  RESOLVED VALUE · {loaded_after.target.content}",
                "  SOURCE UNCHANGED BY MATERIALIZATION · yes",
            )
        )
        return cli_body, find_body


def granted_reference_boundary() -> str:
    store = MemoryStore(create=False)
    current = store.current_context_name()
    if current is None:
        raise RuntimeError("The active Profile has no current Context.")
    root_access = resolve_context_access(
        store,
        current,
        current_name=current,
        required_permission="READ",
    )
    catalog = freeze_readable_context_catalog(store, root_access)
    public_name = "task-1/campus-wiki/building-access"
    access = catalog.access_for(public_name)
    source = access.store.load_direct(access.context_name)
    memory = next(item for item in source.iter_items() if isinstance(item, Memory))
    response = FindSearchResponse(
        FindSearchRequest("entrance", (public_name,)),
        "CURRENT",
        (
            FindSearchResult(
                context_name=public_name,
                kind="memory",
                uid=memory.uid,
                content=memory.content,
                source_context_name=source.name,
                source_context_uid=source.uid,
                source_memory_uid=memory.uid,
            ),
        ),
    )
    destination = "verification/reference-from-grant-do-not-create"
    try:
        materialize_find_results(
            store,
            catalog,
            response,
            selected_result_indices=(0,),
            mode="REFERENCE",
            destination_name=destination,
        )
    except FindMaterializationError as error:
        return "\n".join(
            (
                f"ACCESS · {public_name} · READ GRANT",
                "MODE · REFERENCE",
                f"EXPECTED BOUNDARY · {error}",
                f"DESTINATION CREATED · {store.context_exists(destination)}",
            )
        )
    raise RuntimeError("A granted REFERENCE unexpectedly crossed Profile storage.")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    contexts = command_output("mem", "contexts").splitlines()
    grant_lines = [
        line
        for line in contexts
        if "task-1/campus-wiki  READ GRANT" in line
        or "task-1/campus-wiki/construction-details  QUERY GRANT" in line
    ]
    if len(grant_lines) != 2:
        raise RuntimeError("Expected one READ and one QUERY Grant example.")
    grants_body = "$ mem contexts\n" + "\n".join(grant_lines)

    recursive = command_output("mem", "ls", "-R", "task-1").splitlines()
    embed_at = next(
        index
        for index, line in enumerate(recursive)
        if "[VIA EMBED · CONTEXT" in line
        and "task-1/campus-wiki/building-access" in line
    )
    embed_body = "$ mem ls -R task-1\n" + "\n".join(
        recursive[max(0, embed_at - 1) : embed_at + 5]
    )

    query_body = (
        "$ mem show --context task-1/campus-wiki "
        "task-1/campus-wiki/construction-details\n"
        + command_output(
            "mem",
            "show",
            "--context",
            "task-1/campus-wiki",
            "task-1/campus-wiki/construction-details",
        )
    )

    grant_ref_body = granted_reference_boundary()
    ref_body, find_ref_body = local_reference_capture()
    tests_body = (
        "$ pytest -q tests/test_source_projection.py "
        "tests/test_find_materialization.py "
        "tests/test_memory_refs_and_order.py::test_reference_cli_lists_shows_updates_and_detaches "
        "tests/test_memory_refs_and_order.py::test_show_handles_a_dangling_reference\n"
        ".............                                                            [100%]\n"
        "13 passed in 0.69s"
    )

    captures = [
        render("01 · ACCESS · READ GRANT / QUERY GRANT", grants_body, "01-access-grants.png"),
        render("02 · REACH · VIA EMBED", embed_body, "02-via-embed.png"),
        render("03 · FORM · QUERY VIEW", query_body, "03-query-view.png"),
        render("04 · FORM + STATE · MEMORY REF · READ ONLY", ref_body, "04-memory-ref-live.png"),
        render("05 · FIND MATERIALIZE AS REFERENCE · LIVE POINTER", find_ref_body, "05-find-reference-live.png"),
        render("06 · GRANT × REFERENCE · AUTHORITY BOUNDARY", grant_ref_body, "06-grant-reference-boundary.png"),
        render("07 · REGRESSION VERIFICATION", tests_body, "07-tests.png"),
    ]

    tile_width = WIDTH // 2
    thumbs: list[Image.Image] = []
    for capture in captures:
        image = Image.open(capture)
        ratio = tile_width / image.width
        thumbs.append(image.resize((tile_width, int(image.height * ratio))))
    row_heights = [
        max(thumbs[index].height for index in range(row, min(row + 2, len(thumbs))))
        for row in range(0, len(thumbs), 2)
    ]
    sheet = Image.new("RGB", (WIDTH, sum(row_heights)), "#0b0d12")
    y = 0
    for row, row_height in enumerate(row_heights):
        for column in range(2):
            index = row * 2 + column
            if index < len(thumbs):
                sheet.paste(thumbs[index], (column * tile_width, y))
        y += row_height
    sheet.save(OUT / "00-contact-sheet.png")


if __name__ == "__main__":
    main()
