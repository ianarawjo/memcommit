"""Create the isolated deterministic Context used by the receipt captures."""

from __future__ import annotations

import os
import sys
from pathlib import Path


repository_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(repository_root))

import memcommit.application.capabilities.ops as ops  # noqa: E402
from memcommit.core.context import Memory  # noqa: E402
from memcommit.persistence.store import MemoryStore  # noqa: E402


capture_store = os.environ.get("MEMCOMMIT_CAPTURE_STORE")
if not capture_store:
    raise RuntimeError("MEMCOMMIT_CAPTURE_STORE is required for this capture.")

store = MemoryStore(root=Path(capture_store))
context = ops.init("practice/2")
context.add(
    Memory(
        uid="b925d6bf-aec7-4de5-a432-7cf627d72628",
        content="dfadfadfadfasf",
    )
)
store.create_context(context)
store.set_current(context.name)
