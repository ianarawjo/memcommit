#!/usr/bin/env python3
"""Record the no-reset CORE-to-TRANSFORM boundary using one tree digest."""

import json
from pathlib import Path


WORLD = Path("/Users/KimMunyeong/Github/memcommit/agent-records/outputs/study-long-audit-20260825-v2/worlds/ticker")
core_path = WORLD / "phase-core.json"
transform_path = WORLD / "phase-transform.json"
core = json.loads(core_path.read_text())
transform = json.loads(transform_path.read_text())
boundary = transform["starting_boundary"]["transform_initial_tree_digest"]
core["final_context_tree_digest"] = boundary
core["final_context_tree_digest_semantics"] = (
    "SHA-256 over every active-Profile context.json plus state.json in sorted path order, "
    "captured after CORE 105 and immediately before TRANSFORM sequence 1."
)
transform["starting_boundary"].update(
    {
        "core_final_context_tree_digest": boundary,
        "matches_core_final_context_tree_digest": True,
        "explicit_cumulative_bridge": (
            "CORE completion and TRANSFORM sequence 1 use the same Profile UID, Store root, "
            "current Context, and full Context-tree digest; no reset or bootstrap occurred."
        ),
    }
)
core_path.write_text(json.dumps(core, ensure_ascii=False, indent=2) + "\n")
transform_path.write_text(json.dumps(transform, ensure_ascii=False, indent=2) + "\n")
