from __future__ import annotations

from contextlib import contextmanager
import json

import memcommit.config as config_module
import memcommit.application.ops as ops
import memcommit.study_scenarios.legacy.prewarm.summarize as summarize_prewarm_module
from memcommit.config import Config
from memcommit.context import Context, Memory
from memcommit.store import MemoryStore
from memcommit.study_scenarios.legacy.prewarm.installations import (
    record_declared_installation,
)
from memcommit.study_scenarios.legacy.prewarm.registry import (
    payload_digest,
    publish_artifact,
)
from memcommit.study_scenarios.legacy.prewarm.summarize import (
    build_summarize_prewarm_artifact,
)
from memcommit.summarize import collect_summary_frame
from memcommit.application.operations.summarize.application import SummarizeRequest
from memcommit.application.operations.summarize.runtime import run_summarize_with_store
from memcommit.understanding import UnderstandingSummary


def _configure(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config_module, "CONFIG_FILE", tmp_path / "config.json")
    Config().update(
        {
            "semantic_provider": "codex_chatgpt",
            "codex_chatgpt_model": "gpt-5.6-sol",
            "codex_chatgpt_reasoning_effort": "medium",
        }
    )


def _install_exact(
    store: MemoryStore,
    context: Context,
    *,
    baseline_uid: str,
):
    frame = collect_summary_frame(context)
    understanding = UnderstandingSummary(
        text="The exact frame records its source-grounded commitment.",
        source_uids=tuple(source.memory_uid for source in frame.sources),
    )
    key, artifact = build_summarize_prewarm_artifact(
        task="task-1",
        frame=frame,
        understanding=understanding,
        provider="codex_chatgpt",
        model="gpt-5.6-sol",
        reasoning="medium",
        offline_provider_seconds=1.25,
    )
    entry = publish_artifact(
        store.store_dir,
        baseline_profile_uid=baseline_uid,
        operation="SUMMARIZE",
        task="task-1",
        key=key,
        artifact=artifact,
    )
    record_declared_installation(
        store,
        entry=entry,
        evidence={
            "frame_digest": frame.digest,
            "understanding_digest": payload_digest(understanding.to_dict()),
        },
    )
    return frame, understanding


def test_higher_quality_summarize_materializes_without_opening_provider(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _configure(tmp_path, monkeypatch)
    store = MemoryStore()
    context = ops.init("task-1/summary-source")
    ops.add(context, "Keep this source-grounded commitment.")
    store.create_context(context)
    frame, prepared = _install_exact(
        store,
        context,
        baseline_uid="11111111-1111-4111-8111-111111111111",
    )
    Config().update({"codex_chatgpt_reasoning_effort": "none"})

    def forbidden_provider_session():
        raise AssertionError("exact Summarize prewarm opened the provider")

    result = run_summarize_with_store(
        SummarizeRequest(context_locator=context.name),
        store=store,
        current_context_name=None,
        provider_session_factory=forbidden_provider_session,
    )

    assert result.source_digest == frame.digest
    assert result.understanding == prepared
    assert not (store.store_dir / "summarize-sessions").exists()


def test_recursive_request_does_not_project_a_direct_summarize_artifact(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _configure(tmp_path, monkeypatch)
    store = MemoryStore()
    root = ops.init("task-1/summary-source")
    child = ops.init("task-1/summary-source/child")
    ops.add(root, "The root has one commitment.")
    ops.add(child, "The child has a distinct exception.")
    store.create_context(root)
    store.create_context(child)
    _install_exact(
        store,
        root,
        baseline_uid="11111111-1111-4111-8111-111111111111",
    )
    provider_calls = 0

    class Provider:
        def complete(self, prompt, *, operation, output_schema=None):
            nonlocal provider_calls
            provider_calls += 1
            payload = json.loads(prompt.split("SUMMARIZE CONTEXT PAYLOAD:\n", 1)[1])
            return json.dumps(
                {
                    "text": "The root commitment remains qualified by its child exception.",
                    "source_ids": [row["source_id"] for row in payload["memories"]],
                }
            )

    @contextmanager
    def provider_session():
        yield Provider()

    result = run_summarize_with_store(
        SummarizeRequest(
            context_locator=root.name,
            include_descendants=True,
            follow_embeds=True,
        ),
        store=store,
        current_context_name=None,
        provider_session_factory=provider_session,
    )

    assert provider_calls == 1
    assert result.source_count == 2
    assert result.include_descendants is True


def test_exact_lookup_opens_only_the_requested_artifact(
    isolated_store,
    tmp_path,
    monkeypatch,
):
    _configure(tmp_path, monkeypatch)
    store = MemoryStore()
    first = Context(uid="context-first", name="task-1/first")
    first.add(Memory(uid="memory-first", content="First source."))
    second = Context(uid="context-second", name="task-1/second")
    second.add(Memory(uid="memory-second", content="Second source."))
    store.create_context(first)
    store.create_context(second)
    baseline_uid = "11111111-1111-4111-8111-111111111111"
    _install_exact(store, first, baseline_uid=baseline_uid)
    _install_exact(store, second, baseline_uid=baseline_uid)
    opened: list[str] = []
    original = summarize_prewarm_module.load_artifact

    def tracking_load(store_root, entry):
        opened.append(entry.key)
        return original(store_root, entry)

    monkeypatch.setattr(summarize_prewarm_module, "load_artifact", tracking_load)
    result = summarize_prewarm_module.find_declared_summarize_prewarm(
        store=store,
        frame=collect_summary_frame(second),
    )

    assert result is not None
    assert len(opened) == 1
