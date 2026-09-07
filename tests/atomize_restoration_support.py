"""Build retained Save As records without reviving the removed console route."""

from __future__ import annotations

import copy
from dataclasses import replace
import json
from types import SimpleNamespace

from memcommit.application.capabilities.command_recovery import build_command_stacks
from memcommit.application.capabilities import ops
from memcommit.application.operations.atomize.domain import (
    create_atomize_analysis,
    impact_atomize,
)
from memcommit.application.operations.atomize.records import (
    AtomizeReviewRecord,
    atomize_review_issue_projection,
    atomize_review_record_digest,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.records import context_record_digest


class _AtomicProvider:
    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        payload = json.loads(prompt.split("ATOMIZE IMPACT PAYLOAD:\n", 1)[1])
        ids = [item["candidate_id"] for item in payload["memories"]]
        return json.dumps(
            {
                "overview": {
                    "understood": {"text": "One source fact.", "source_ids": ids},
                    "changed": {"text": "The fact is preserved.", "source_ids": ids},
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": uid,
                        "classification": "ATOMIC",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [],
                        "reason": "One independently revisable fact.",
                    }
                    for uid in ids
                ],
                "quality_issues": [],
            }
        )


def create_save_as(*, with_workbench=True):
    store = MemoryStore()
    source = ops.init("atomize/source")
    ops.add(source, "The library closes at five.")
    store.save(source)
    store.set_current(source.name)
    analysis = create_atomize_analysis(source, impact_atomize(source, _AtomicProvider))
    store.save_atomize_analysis(analysis)
    reviewing = (
        AtomizeReviewRecord.create(
            analysis_uid=analysis.uid,
            context_uid=source.uid,
            context_name=source.name,
            context_digest=analysis.context_digest,
            issues=atomize_review_issue_projection(analysis),
        )
        if with_workbench
        else None
    )
    output = ops.init("atomize/output")
    for item in source.iter_items():
        output.add(copy.deepcopy(item))
    args = {
        "analysis_uid": analysis.uid,
        "context_creation": {
            "version": 1,
            "context_uid": output.uid,
            "context_name": output.name,
        },
        "atomize_save_as": {
            "version": 1,
            "source_context": {
                "uid": source.uid,
                "name": source.name,
                "digest": context_record_digest(source),
            },
            "source_frame": source.to_dict(),
            "source_frame_digest": context_record_digest(source),
            "source_analysis_uid": analysis.uid,
            "source_workbench": None
            if reviewing is None
            else {
                "uid": reviewing.uid,
                "output_context_name": reviewing.output_context_name,
                "record_digest": atomize_review_record_digest(reviewing),
            },
            "current_before": source.name,
        },
    }
    checkpoint = store.save(
        output,
        AutoCheckpoint(
            command="atomize",
            args=args,
            description="Retained Atomize Save As result",
        ),
    )
    store.save_atomize_analysis(
        replace(
            analysis,
            context_uid=output.uid,
            context_name=output.name,
        )
    )
    terminal = copy.deepcopy(reviewing)
    if terminal is not None:
        terminal.output_context_name = output.name
        terminal.record_application(
            output_context_name=output.name,
            checkpoint_uid=checkpoint.uid,
        )
        store.save_atomize_workbench(terminal)
    store.set_current(output.name)
    return SimpleNamespace(
        store=store,
        source=source,
        output=output,
        analysis=analysis,
        reviewing=reviewing,
        terminal=terminal,
        checkpoint=checkpoint,
        unit=build_command_stacks(store).undo[-1],
        archive=store._command_context_archive_path(checkpoint.uid),
    )


def snapshot_records(store):
    return {
        str(path.relative_to(store.store_dir)): json.loads(path.read_text())
        for path in store.store_dir.rglob("*.json")
    }
