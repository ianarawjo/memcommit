"""Exercise an installed ``mem-mcp`` entry point through the official client."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import uuid

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

import memcommit
import memcommit.ops as ops
from memcommit.api import MemCommitClient
from memcommit.atomize_grounding import (
    AtomizeGroundingAnchor,
    AtomizeGroundingBindings,
    AtomizeGroundingSession,
)
from memcommit.store import MemoryStore


_ATOMIZE_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class _AtomizeProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert output_schema is not None
        payload = json.loads(prompt.split(_ATOMIZE_PAYLOAD_MARKER, 1)[1])
        items = []
        for source in payload["memories"]:
            left, right = source["content"].split(" and ", 1)
            items.append(
                {
                    "candidate_id": source["candidate_id"],
                    "classification": "COMPOSITE",
                    "reason_codes": ["A01_ONE_FOCUS"],
                    "children": [
                        {"content": left, "source_spans": [left]},
                        {"content": right, "source_spans": [right]},
                    ],
                    "reason": "The source contains two independent facts.",
                }
            )
        aliases = [source["candidate_id"] for source in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "The Memory contains two installed-smoke facts.",
                        "source_ids": aliases,
                    },
                    "changed": {
                        "text": "The composite Memory will be split.",
                        "source_ids": aliases,
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": items,
                "quality_issues": [],
            }
        )


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
    store.save(ops.init("smoke/forget-empty"))
    store.set_current(context.name)
    digest = "0" * 64
    grounding = AtomizeGroundingSession.create(
        bindings=AtomizeGroundingBindings(
            context_uid=context.uid,
            context_name=context.name,
            context_digest=digest,
            analysis_uid=str(uuid.uuid4()),
            analysis_digest=digest,
            workbench_uid=str(uuid.uuid4()),
            workbench_digest=digest,
            response_digest=digest,
        ),
        anchor=AtomizeGroundingAnchor(
            issue_uid="ambiguity:installed-smoke",
            kind="AMBIGUITY",
            arity="UNARY",
            source_uids=(str(uuid.uuid4()),),
            issue_digest=digest,
        ),
    )
    grounding.keep_review_only()
    store.save_atomize_grounding_session(grounding)
    atomize_client = MemCommitClient(
        root=root,
        semantic_provider_factory=_AtomizeProvider,
    )
    for name in ("smoke/atomize", "smoke/atomize-save-as"):
        atomize_context = ops.init(name)
        ops.add(
            atomize_context,
            "The installed library closes at five and the installed cafe closes at six.",
        )
        store.save(atomize_context)
        prepared = atomize_client.open_atomize_analysis(atomize_context.name)
        assert prepared.origin == "PROVIDER"
        assert store.list_checkpoints(atomize_context.name) == []
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
            help_result = await session.call_tool(
                "memcommit_help",
                {"version": 1, "kind": "describe", "operation": "compare"},
            )
            added = await session.call_tool(
                "memcommit_add_memories",
                {
                    "version": 1,
                    "kind": "memories",
                    "contents": ["First installed MCP Memory.", "Second Memory."],
                    "context_name": "smoke/target",
                },
            )
            shown = await session.call_tool(
                "memcommit_show",
                {
                    "version": 1,
                    "kind": "inspect",
                    "context_name": "smoke/target",
                },
            )
            grounding = await session.call_tool(
                "memcommit_atomize_grounding",
                {
                    "version": 1,
                    "kind": "open",
                    "context_name": "smoke/target",
                },
            )
            atomize = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "open",
                    "context_name": "smoke/atomize",
                },
            )
            atomize_version = atomize.structured_content["result"]["version"]
            atomize_apply = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "apply_as_is",
                    "context_name": "smoke/atomize",
                    "expected_version": atomize_version,
                },
            )
            atomize_retry = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "apply_as_is",
                    "context_name": "smoke/atomize",
                    "expected_version": atomize_version,
                },
            )
            atomize_save_source = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "open",
                    "context_name": "smoke/atomize-save-as",
                },
            )
            save_source_result = atomize_save_source.structured_content["result"]
            atomize_response = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "respond",
                    "context_name": "smoke/atomize-save-as",
                    "expected_version": save_source_result["version"],
                    "issue_uid": save_source_result["issues"][0]["uid"],
                    "option_uid": None,
                    "comment": "Keep the two installed facts independent.",
                },
            )
            response_proposal = atomize_response.structured_content["result"][
                "proposal"
            ]
            atomize_output_plan = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "plan_output",
                    "context_name": "smoke/atomize-save-as",
                    "expected_version": response_proposal["version"],
                    "output_context_name": "smoke/atomize-output",
                },
            )
            output_proposal = atomize_output_plan.structured_content["result"][
                "proposal"
            ]
            atomize_save = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "save_as",
                    "context_name": "smoke/atomize-save-as",
                    "expected_version": output_proposal["version"],
                },
            )
            atomize_save_retry = await session.call_tool(
                "memcommit_atomize",
                {
                    "version": 1,
                    "kind": "save_as",
                    "context_name": "smoke/atomize-save-as",
                    "expected_version": output_proposal["version"],
                },
            )
            forget = await session.call_tool(
                "memcommit_forget",
                {
                    "version": 1,
                    "kind": "analyze",
                    "instruction": "Forget any obsolete detail.",
                    "context_name": "smoke/forget-empty",
                },
            )
            forget_result = forget.structured_content["result"]
            forget_apply_request = {
                "version": 1,
                "kind": "apply",
                "review_uid": forget_result["review_uid"],
                "expected_version": forget_result["version"],
            }
            forget_apply = await session.call_tool(
                "memcommit_forget",
                forget_apply_request,
            )
            forget_retry = await session.call_tool(
                "memcommit_forget",
                forget_apply_request,
            )
            unknown = await session.call_tool("not_registered", {})

    assert initialized.server_info.name == "memcommit"
    assert [tool.name for tool in listed.tools] == [
        "memcommit_help",
        "memcommit_show",
        "memcommit_find",
        "memcommit_replace",
        "memcommit_search",
        "memcommit_query",
        "memcommit_quality_find",
        "memcommit_add_memories",
        "memcommit_compare",
        "memcommit_meld",
        "memcommit_atomize",
        "memcommit_atomize_grounding",
        "memcommit_distill",
        "memcommit_elaborate",
        "memcommit_fit",
        "memcommit_forget",
        "memcommit_resolve",
        "memcommit_dedup",
    ]
    assert help_result.is_error is False
    assert help_result.structured_content["result"]["operation"]["name"] == "compare"
    assert help_result.structured_content["result"]["effect"] == "NONE"
    assert added.is_error is False
    assert added.structured_content["ok"] is True
    assert shown.is_error is False
    assert shown.structured_content["result"]["kind"] == "context"
    assert [
        item["content"] for item in shown.structured_content["result"]["items"]
    ] == ["First installed MCP Memory.", "Second Memory."]
    assert shown.structured_content["result"]["effect"] == "NONE"
    assert grounding.is_error is False
    assert grounding.structured_content["ok"] is True
    assert grounding.structured_content["result"]["session"]["state"] == (
        "KEPT_REVIEW_ONLY"
    )
    assert atomize.is_error is False
    assert atomize.structured_content["result"]["origin"] == "SAVED"
    assert atomize.structured_content["result"]["cache_used"] is True
    assert atomize.structured_content["result"]["provider_used"] is False
    assert atomize_apply.is_error is False
    assert atomize_apply.structured_content["result"]["recovered"] is False
    assert atomize_retry.is_error is False
    assert atomize_retry.structured_content["result"]["recovered"] is True
    assert atomize_retry.structured_content["result"]["checkpoint_uid"] == (
        atomize_apply.structured_content["result"]["checkpoint_uid"]
    )
    assert atomize_save_source.is_error is False
    assert save_source_result["cache_used"] is True
    assert atomize_response.is_error is False
    assert response_proposal["issues"][0]["answered"] is True
    assert atomize_output_plan.is_error is False
    assert output_proposal["output_context_name"] == "smoke/atomize-output"
    assert output_proposal["in_place_apply_allowed"] is False
    assert atomize_save.is_error is False
    assert atomize_save.structured_content["result"]["created_context"] is True
    assert atomize_save.structured_content["result"]["recovered"] is False
    assert atomize_save_retry.is_error is False
    assert atomize_save_retry.structured_content["result"]["recovered"] is True
    assert atomize_save_retry.structured_content["result"]["checkpoint_uid"] == (
        atomize_save.structured_content["result"]["checkpoint_uid"]
    )
    assert forget.is_error is False
    assert forget_result["retention"] == "PROCESS_LOCAL"
    assert forget_result["provider_used"] is False
    assert forget_result["candidates"] == []
    assert forget_result["effect"] == "NONE"
    assert forget_apply.is_error is False
    assert forget_apply.structured_content["result"]["applied"] is False
    assert forget_apply.structured_content["result"]["changed_count"] == 0
    assert forget_apply.structured_content["result"]["recovered"] is False
    assert forget_apply.structured_content["result"]["effect"] == "NONE"
    assert forget_retry.is_error is False
    assert forget_retry.structured_content["result"]["recovered"] is True
    assert forget_retry.structured_content["result"]["effect"] == "NONE"
    assert unknown.is_error is True
    assert unknown.structured_content["error"]["code"] == "unknown_tool"
    return {
        "server_name": initialized.server_info.name,
        "server_version": initialized.server_info.version,
        "tools": [tool.name for tool in listed.tools],
        "help": help_result.structured_content,
        "add": added.structured_content,
        "show": shown.structured_content,
        "atomize_grounding": grounding.structured_content,
        "atomize": atomize.structured_content,
        "atomize_apply": atomize_apply.structured_content,
        "atomize_retry": atomize_retry.structured_content,
        "atomize_save_source": atomize_save_source.structured_content,
        "atomize_response": atomize_response.structured_content,
        "atomize_output_plan": atomize_output_plan.structured_content,
        "atomize_save": atomize_save.structured_content,
        "atomize_save_retry": atomize_save_retry.structured_content,
        "forget": forget.structured_content,
        "forget_apply": forget_apply.structured_content,
        "forget_retry": forget_retry.structured_content,
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
    atomized = store.load_direct("smoke/atomize")
    atomize_checkpoints = store.list_checkpoints(atomized.name)
    assert [memory.content for memory in atomized.memories.values()] == [
        "The installed library closes at five",
        "the installed cafe closes at six.",
    ]
    assert len(atomize_checkpoints) == 1
    assert atomize_checkpoints[0]["uid"] == (
        protocol["atomize_apply"]["result"]["checkpoint_uid"]
    )
    save_source = store.load_direct("smoke/atomize-save-as")
    assert [memory.content for memory in save_source.memories.values()] == [
        "The installed library closes at five and the installed cafe closes at six."
    ]
    assert store.list_checkpoints(save_source.name) == []
    saved_output = store.load_direct("smoke/atomize-output")
    save_checkpoints = store.list_checkpoints(saved_output.name)
    assert [memory.content for memory in saved_output.memories.values()] == [
        "The installed library closes at five",
        "the installed cafe closes at six.",
    ]
    assert len(save_checkpoints) == 1
    assert save_checkpoints[0]["uid"] == (
        protocol["atomize_save"]["result"]["checkpoint_uid"]
    )
    assert store.current_context_name() == "smoke/atomize-output"
    forgotten = store.load_direct("smoke/forget-empty")
    assert forgotten.memories == {}
    assert store.list_checkpoints(forgotten.name) == []

    print(
        json.dumps(
            {
                "ok": True,
                "memcommit_origin": str(origin),
                "mcp_sdk_version": importlib.metadata.version("mcp"),
                "entrypoint": command,
                "checkpoint_count": len(checkpoints),
                "atomize_checkpoint_count": len(atomize_checkpoints),
                "atomize_save_checkpoint_count": len(save_checkpoints),
                "forget_checkpoint_count": 0,
                **protocol,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
