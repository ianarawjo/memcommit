"""
    ContextStore manages all persistence for mem contexts.
    Single source of truth for reading/writing ~/.mem/.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from memcommit.context import Checkpoint, Context, Information, Memory

STORE_DIR = Path.home() / ".mem"
CONTEXTS_DIR = STORE_DIR / "contexts"
STATE_FILE = STORE_DIR / "state.json"


class ContextStore:

    def __init__(self):
        STORE_DIR.mkdir(exist_ok=True)
        CONTEXTS_DIR.mkdir(exist_ok=True)
        if not STATE_FILE.exists():
            self._write_state({"current": None})

    # --- State ---

    def _read_state(self) -> dict:
        with open(STATE_FILE) as f:
            return json.load(f)

    def _write_state(self, state: dict) -> None:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def current_context_name(self) -> Optional[str]:
        return self._read_state().get("current")

    def set_current(self, name: str) -> None:
        state = self._read_state()
        state["current"] = name
        self._write_state(state)

    # --- Context paths ---

    def _context_dir(self, name: str) -> Path:
        return CONTEXTS_DIR / name

    def _context_file(self, name: str) -> Path:
        return self._context_dir(name) / "context.json"

    def context_exists(self, name: str) -> bool:
        return self._context_file(name).exists()

    def list_context_names(self) -> list[str]:
        return sorted(
            d.name for d in CONTEXTS_DIR.iterdir()
            if d.is_dir() and (d / "context.json").exists()
        )

    # --- Serialization ---

    def _serialize_context(self, ctx: Context) -> dict:
        """Serialize a context to a JSON-safe dict; embedded contexts stored as refs."""
        memories: dict[str, dict] = {}
        for uid, info in ctx.memories.items():
            if isinstance(info, Memory):
                memories[uid] = {"type": "memory", "uid": info.uid, "content": info.content}
            elif isinstance(info, Context):
                memories[uid] = {"type": "context_ref", "uid": info.uid, "name": info.name}
        return {"uid": ctx.uid, "name": ctx.name, "memories": memories}

    def _deserialize_context(self, data: dict, _loading: frozenset[str] = frozenset()) -> Context:
        """Deserialize a context, resolving context_refs as live loads from disk."""
        ctx = Context(uid=data["uid"], name=data["name"])
        for uid, item in data["memories"].items():
            if item["type"] == "memory":
                ctx.add(Memory(uid=item["uid"], content=item["content"]))
            elif item["type"] == "context_ref":
                ref_name = item["name"]
                if ref_name in _loading:
                    # Circular reference — skip silently to avoid infinite recursion.
                    continue
                if self.context_exists(ref_name):
                    nested = self.load_context(ref_name, _loading | {ctx.name})
                    ctx.add(nested)
        return ctx

    # --- Load / Save ---

    def load_context(self, name: str, _loading: frozenset[str] = frozenset()) -> Context:
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        return self._deserialize_context(data, _loading)

    def save_context(self, ctx: Context) -> None:
        ctx_dir = self._context_dir(ctx.name)
        ctx_dir.mkdir(exist_ok=True)
        (ctx_dir / "checkpoints").mkdir(exist_ok=True)
        with open(self._context_file(ctx.name), "w") as f:
            json.dump(self._serialize_context(ctx), f, indent=2)

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load_context(name)

    # --- Checkpoints ---

    def save_checkpoint(self, ctx: Context, message: str = "") -> Checkpoint:
        cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=self._serialize_context(ctx),
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = message[:24].replace(" ", "-").replace("/", "-") if message else "checkpoint"
        cp_dir = self._context_dir(ctx.name) / "checkpoints"
        cp_dir.mkdir(exist_ok=True)
        with open(cp_dir / f"{ts}-{slug}.json", "w") as f:
            json.dump({
                "uid": cp.uid,
                "message": cp.message,
                "timestamp": cp.timestamp.isoformat(),
                "snapshot": cp.snapshot,
            }, f, indent=2)
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        cp_dir = self._context_dir(name) / "checkpoints"
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            with open(path) as f:
                entries.append(json.load(f))
        return sorted(entries, key=lambda x: x["timestamp"])
