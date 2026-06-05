"""
    MemoryStore manages all persistence for mem contexts.
    Single source of truth for reading/writing ~/.mem/.

    Serialization is delegated to Context.to_dict() / Context.from_dict().
    All disk I/O is explicit: callers must call store.save(ctx) to persist mutations.
"""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from memcommit.context import Checkpoint, Context

STORE_DIR = Path.home() / ".mem"
CONTEXTS_DIR = STORE_DIR / "contexts"
STATE_FILE = STORE_DIR / "state.json"


class MemoryStore:

    def __init__(self):
        STORE_DIR.mkdir(exist_ok=True)
        CONTEXTS_DIR.mkdir(exist_ok=True)
        if not STATE_FILE.exists():
            self._write_state({"current": None})

    # --- Global state ---

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

    # --- Load / Save ---

    def load(self, name: str, _loading: frozenset[str] = frozenset()) -> Context:
        """Load a context by name, resolving embedded context refs as live loads."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)

        def loader(ref_name: str) -> Context | None:
            if ref_name in _loading:
                return None  # break circular reference
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name, _loading | {name})

        return Context.from_dict(data, loader=loader)

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load(name)

    def save(self, ctx: Context) -> None:
        """Persist a context to disk. Caller is responsible for calling this after mutations."""
        ctx_dir = self._context_dir(ctx.name)
        ctx_dir.mkdir(exist_ok=True)
        (ctx_dir / "checkpoints").mkdir(exist_ok=True)
        with open(self._context_file(ctx.name), "w") as f:
            json.dump(ctx.to_dict(), f, indent=2)

    def delete(self, name: str) -> None:
        """Delete a context and all its data from disk. Clears current if it matches."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        shutil.rmtree(self._context_dir(name))
        if self.current_context_name() == name:
            self._write_state({"current": None})

    # --- Checkpoints ---

    def checkpoint(self, ctx: Context, message: str = "") -> Checkpoint:
        """Save a point-in-time snapshot of ctx's current state."""
        cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
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
