"""Exercise an installed ``mem-mcp`` entry point through the official client."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

import memcommit
import memcommit.ops as ops
from memcommit.store import MemoryStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--forbid-origin", type=Path, required=True)
    return parser


def _assert_installed_origin(forbidden: Path) -> Path:
    origin = Path(memcommit.__file__).resolve()
    try:
        origin.relative_to(forbidden.resolve())
    except ValueError:
        return origin
    raise AssertionError(f"Smoke test imported the source checkout: {origin}")


def _prepare_store(root: Path) -> MemoryStore:
    store = MemoryStore(root=root)
    context = ops.init("smoke/target")
    store.save(context)
    store.set_current(context.name)
    assert store.list_checkpoints(context.name) == []
    return store


async def _exercise_stdio(command: str, root: Path, workdir: Path) -> dict[str, object]:
    parameters = StdioServerParameters(
        command=command,
        args=["--root", str(root)],
        cwd=workdir,
    )
    async with stdio_client(parameters) as streams:
        async with ClientSession(*streams) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            added = await session.call_tool(
                "memcommit_add_memories",
                {
                    "version": 1,
                    "kind": "memories",
                    "contents": ["First installed MCP Memory.", "Second Memory."],
                    "context_name": "smoke/target",
                },
            )
            unknown = await session.call_tool("not_registered", {})

    assert initialized.server_info.name == "memcommit"
    assert [tool.name for tool in listed.tools] == [
        "memcommit_query",
        "memcommit_add_memories",
    ]
    assert added.is_error is False
    assert added.structured_content["ok"] is True
    assert unknown.is_error is True
    assert unknown.structured_content["error"]["code"] == "unknown_tool"
    return {
        "server_name": initialized.server_info.name,
        "server_version": initialized.server_info.version,
        "tools": [tool.name for tool in listed.tools],
        "add": added.structured_content,
        "unknown_error": unknown.structured_content["error"],
    }


def main() -> int:
    arguments = _parser().parse_args()
    origin = _assert_installed_origin(arguments.forbid_origin)
    store = _prepare_store(arguments.store)
    command = shutil.which("mem-mcp")
    if command is None:
        raise AssertionError("The installed environment has no mem-mcp entry point.")

    protocol = anyio.run(
        _exercise_stdio,
        command,
        arguments.store.resolve(),
        arguments.workdir.resolve(),
    )
    saved = store.load_direct("smoke/target")
    checkpoints = store.list_checkpoints(saved.name)
    assert [memory.content for memory in saved.memories.values()] == [
        "First installed MCP Memory.",
        "Second Memory.",
    ]
    assert len(checkpoints) == 1
    assert checkpoints[0]["uid"] == protocol["add"]["result"]["checkpoint_uid"]

    print(
        json.dumps(
            {
                "ok": True,
                "memcommit_origin": str(origin),
                "mcp_sdk_version": importlib.metadata.version("mcp"),
                "entrypoint": command,
                "checkpoint_count": len(checkpoints),
                **protocol,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
