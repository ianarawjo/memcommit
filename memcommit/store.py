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

from memcommit.context import AutoCheckpoint, Checkpoint, Context

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

    def save(self, ctx: Context, auto_checkpoint: Optional[AutoCheckpoint] = None) -> None:
        """Persist a context to disk. Caller is responsible for calling this after mutations."""
        ctx_dir = self._context_dir(ctx.name)
        ctx_dir.mkdir(exist_ok=True)
        (ctx_dir / "checkpoints").mkdir(exist_ok=True)
        if auto_checkpoint is not None:
            self.checkpoint(
                ctx,
                message=auto_checkpoint.description,
                command=auto_checkpoint.command,
                args=auto_checkpoint.args,
                description=auto_checkpoint.description,
                auto=True,
            )
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

    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
    ) -> Checkpoint:
        """Save a point-in-time snapshot of ctx's current state."""
        cp = Checkpoint(
            uid=str(uuid.uuid4()),
            message=message,
            timestamp=datetime.now(),
            snapshot=ctx.to_dict(),
            command=command,
            args=args,
            description=description,
            auto=auto,
        )
        ts = cp.timestamp.strftime("%Y%m%dT%H%M%S")
        slug = message[:24].replace(" ", "-").replace("/", "-") if message else (command or "checkpoint")
        cp_dir = self._context_dir(ctx.name) / "checkpoints"
        cp_dir.mkdir(exist_ok=True)
        with open(cp_dir / f"{ts}-{slug}.json", "w") as f:
            json.dump({
                "uid": cp.uid,
                "message": cp.message,
                "timestamp": cp.timestamp.isoformat(),
                "snapshot": cp.snapshot,
                "command": cp.command,
                "args": cp.args,
                "description": cp.description,
                "auto": cp.auto,
            }, f, indent=2)
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        """Return checkpoints for a context, sorted newest-first."""
        cp_dir = self._context_dir(name) / "checkpoints"
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            with open(path) as f:
                entries.append(json.load(f))
        return sorted(entries, key=lambda x: x["timestamp"], reverse=True)

    def revert(
        self, ctx_name: str, uid_prefix: str, keep_history: bool = False
    ) -> tuple[Checkpoint, Checkpoint]:
        """Revert context to a checkpoint. Returns (pre_revert_cp, target_cp).

        By default, checkpoints newer than the target are removed and the
        pre-revert snapshot is appended as the new head. If the target is itself
        a pre-revert checkpoint carrying a log_snapshot, the full original log
        is rebuilt from that snapshot instead of just truncating.

        Pass keep_history=True to leave all checkpoint files untouched.
        """
        entries = self.list_checkpoints(ctx_name)  # captured before any mutations
        matches = [e for e in entries if e["uid"].startswith(uid_prefix)]
        if not matches:
            raise KeyError(f"No checkpoint with uid prefix '{uid_prefix}'.")
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous prefix '{uid_prefix}' matches {len(matches)} checkpoints."
            )

        target_data = matches[0]
        target_ts = target_data["timestamp"]
        ctx = self.load(ctx_name)
        cp_dir = self._context_dir(ctx_name) / "checkpoints"

        if not keep_history:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")

            if log_snapshot is not None:
                # Target carries a log snapshot — fully restore the log from it
                for path in cp_dir.glob("*.json"):
                    path.unlink()
                for entry in sorted(log_snapshot, key=lambda x: x["timestamp"]):
                    ts_file = datetime.fromisoformat(entry["timestamp"]).strftime("%Y%m%dT%H%M%S")
                    fname = f"{ts_file}-{entry['uid'][:8]}.json"
                    with open(cp_dir / fname, "w") as f:
                        json.dump(entry, f, indent=2)
            else:
                # Simple truncation: remove checkpoints newer than target
                for path in cp_dir.glob("*.json"):
                    with open(path) as f:
                        entry_data = json.load(f)
                    if entry_data["timestamp"] > target_ts:
                        path.unlink()

        # Strip nested log_snapshots before storing to prevent recursive size growth
        thin_entries = []
        for e in entries:
            args = e.get("args") or {}
            if "log_snapshot" in args:
                e = {**e, "args": {k: v for k, v in args.items() if k != "log_snapshot"}}
            thin_entries.append(e)

        pre_cp = self.checkpoint(
            ctx,
            message=f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo",
            command="revert",
            args={"target_uid": target_data["uid"], "log_snapshot": thin_entries},
            description=f"Pre-revert to [{target_data['uid'][:8]}] — revert here to undo",
            auto=True,
        )

        def loader(ref_name: str) -> "Context | None":
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name)

        restored = Context.from_dict(target_data["snapshot"], loader=loader)
        self.save(restored)

        target_cp = Checkpoint(
            uid=target_data["uid"],
            message=target_data.get("message", ""),
            timestamp=datetime.fromisoformat(target_data["timestamp"]),
            snapshot=target_data["snapshot"],
            command=target_data.get("command"),
            args=target_data.get("args"),
            description=target_data.get("description"),
            auto=target_data.get("auto", False),
        )
        return pre_cp, target_cp
