"""Exercise structural Atomize from an installed wheel, outside its checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import memcommit
import memcommit.ops as ops
from memcommit import MemCommitClient
from memcommit.store import MemoryStore


_PAYLOAD_MARKER = "ATOMIZE IMPACT PAYLOAD:\n"


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt, *, operation, output_schema=None):
        assert operation == "impact_atomize"
        assert output_schema is not None
        self.calls += 1
        payload = json.loads(prompt.split(_PAYLOAD_MARKER, 1)[1])
        source = payload["memories"][0]
        left, right = source["content"].split(" and ", 1)
        return json.dumps(
            {
                "overview": {
                    "understood": {
                        "text": "One Memory contains two closing times.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "changed": {
                        "text": "The Memory will be split.",
                        "source_ids": [source["candidate_id"]],
                    },
                    "unresolved": {"text": "", "source_ids": []},
                },
                "items": [
                    {
                        "candidate_id": source["candidate_id"],
                        "classification": "COMPOSITE",
                        "reason_codes": ["A01_ONE_FOCUS"],
                        "children": [
                            {"content": left, "source_spans": [left]},
                            {"content": right, "source_spans": [right]},
                        ],
                        "reason": "The source has two revisable facts.",
                    }
                ],
                "quality_issues": [],
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--forbid-origin", type=Path, required=True)
    arguments = parser.parse_args()

    origin = Path(memcommit.__file__).resolve()
    try:
        origin.relative_to(arguments.forbid_origin.resolve())
    except ValueError:
        pass
    else:
        raise AssertionError(f"Smoke test imported the source checkout: {origin}")

    store = MemoryStore(root=arguments.store)
    context = ops.init("installed/atomize")
    ops.add(context, "The library closes at five and the cafe closes at six.")
    store.save(context)
    store.set_current(context.name)
    provider = _Provider()
    client = MemCommitClient(
        root=arguments.store,
        semantic_provider_factory=lambda: provider,
    )

    proposal = client.open_atomize_analysis()
    resumed = MemCommitClient(
        root=arguments.store,
        semantic_provider_factory=lambda: (_ for _ in ()).throw(
            AssertionError("saved resume opened a provider")
        ),
    ).open_atomize_analysis(context.name)
    first = client.apply_atomize_as_is(proposal)
    retry = client.apply_atomize_as_is(proposal)

    assert proposal.origin == "PROVIDER"
    assert resumed.origin == "SAVED"
    assert provider.calls == 1
    assert first.recovered is False
    assert retry.recovered is True
    assert retry.checkpoint_uid == first.checkpoint_uid
    assert len(store.list_checkpoints(context.name)) == 1
    print(
        json.dumps(
            {
                "ok": True,
                "memcommit_origin": str(origin),
                "analysis_origin": proposal.origin,
                "resume_origin": resumed.origin,
                "provider_calls": provider.calls,
                "checkpoint_uid": first.checkpoint_uid,
                "retry_recovered": retry.recovered,
                "result_contents": [
                    memory.content
                    for memory in store.load_direct(context.name).memories.values()
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
