"""
    MemoryStore manages all persistence for mem contexts.
    Single source of truth for reading/writing ~/.mem/.

    Serialization is delegated to Context.to_dict() / Context.from_dict().
    All disk I/O is explicit: callers must call store.save(ctx) to persist mutations.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from memcommit.context import AutoCheckpoint, Checkpoint, Context, Memory

STORE_DIR = Path.home() / ".mem"
CONTEXTS_DIR = STORE_DIR / "contexts"
STATE_FILE = STORE_DIR / "state.json"
QUERY_SOURCES_DIR = STORE_DIR / "query-sources"
IMPACT_PLAN_FILE = STORE_DIR / "impact-plan.json"
STAGED_UPDATE_FILE = STORE_DIR / "staged-update.json"
RESERVED_CONTEXT_SEGMENTS = frozenset({"context.json", "checkpoints"})


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build a JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _write_json_atomic(path: Path, data: object) -> None:
    """Write JSON through a same-directory temporary file, then replace."""
    temporary = path.parent / f".{path.name}.write-{uuid.uuid4().hex}"
    try:
        with open(temporary, "x", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _context_name_parts(name: str) -> tuple[str, ...]:
    """Validate a Context name and return its POSIX namespace segments."""
    if not isinstance(name, str) or not name:
        raise ValueError("Context name must be a non-empty relative path.")
    if "\\" in name:
        raise ValueError(
            f"Invalid context name '{name}': use '/' as the namespace separator."
        )
    if ":" in name:
        raise ValueError(
            f"Invalid context name '{name}': ':' is not allowed in context names."
        )

    parts = tuple(name.split("/"))
    if any(part == "" for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': leading, trailing, or repeated '/' "
            "is not allowed."
        )
    if any(part in {".", ".."} for part in parts):
        raise ValueError(
            f"Invalid context name '{name}': '.' and '..' segments are not allowed."
        )
    reserved = [
        part
        for part in parts
        if part.casefold() in RESERVED_CONTEXT_SEGMENTS
    ]
    if reserved:
        raise ValueError(
            f"Invalid context name '{name}': '{reserved[0]}' is reserved for "
            "Context storage."
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ValueError(
            f"Invalid context name '{name}': control characters are not allowed."
        )
    return parts


def _validate_context_header(data: object, expected_name: str) -> dict:
    """Validate the minimum Context JSON structure needed for safe loading."""
    if not isinstance(data, dict):
        raise ValueError(
            f"Context file for '{expected_name}' must contain a JSON object."
        )
    if data.get("name") != expected_name:
        raise ValueError(
            f"Context file for '{expected_name}' declares a different name "
            f"('{data.get('name')}')."
        )
    if not isinstance(data.get("uid"), str) or not data["uid"]:
        raise ValueError(
            f"Context file for '{expected_name}' has no valid uid."
        )
    if not isinstance(data.get("memories"), dict):
        raise ValueError(
            f"Context file for '{expected_name}' has no valid memories object."
        )
    return data


@dataclass(frozen=True)
class QuerySource:
    """Research-only source text kept outside the normal Context namespace."""

    uid: str
    name: str
    content: str


class MemoryStore:

    def __init__(self, *, create: bool = True):
        """
        Open the store.

        Normal commands create missing store infrastructure. Read-only
        inspection commands can pass create=False to guarantee that merely
        checking absent state does not create ~/.mem or state.json.
        """
        if create:
            STORE_DIR.mkdir(parents=True, exist_ok=True)
            CONTEXTS_DIR.mkdir(parents=True, exist_ok=True)
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

    # --- Semantic update sessions ---

    @staticmethod
    def _load_update_session(path: Path):
        """Load and validate one cached semantic update session."""
        from memcommit.update import UpdateSession

        if not path.exists():
            return None
        if not path.is_file() or path.is_symlink():
            raise ValueError("Semantic update session storage is invalid.")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f, object_pairs_hook=_reject_duplicate_json_keys)
        except (json.JSONDecodeError, ValueError) as error:
            raise ValueError("Semantic update session is invalid JSON.") from error
        try:
            return UpdateSession.from_dict(data)
        except ValueError as error:
            raise ValueError("Semantic update session is invalid.") from error

    @staticmethod
    def _save_update_session(path: Path, session) -> None:
        """Atomically persist one validated semantic update session."""
        from memcommit.update import UpdateSession

        if not isinstance(session, UpdateSession):
            raise TypeError("Expected an UpdateSession.")
        if path.exists() and (not path.is_file() or path.is_symlink()):
            raise ValueError("Semantic update session storage is invalid.")
        _write_json_atomic(path, session.to_dict())

    def load_impact_plan(self):
        """Return the cached impact plan, or None when no plan exists."""
        return self._load_update_session(IMPACT_PLAN_FILE)

    def save_impact_plan(self, session) -> None:
        """Atomically cache a non-mutating impact plan."""
        self._save_update_session(IMPACT_PLAN_FILE, session)

    def load_staged_update(self):
        """Return the active staged update, or None when none exists."""
        return self._load_update_session(STAGED_UPDATE_FILE)

    def save_staged_update(self, session) -> None:
        """Atomically save the active staged update."""
        self._save_update_session(STAGED_UPDATE_FILE, session)

    # --- Context paths ---

    def _context_dir(self, name: str) -> Path:
        parts = _context_name_parts(name)
        path = CONTEXTS_DIR.joinpath(*parts)
        candidate = CONTEXTS_DIR
        for part in parts:
            candidate /= part
            if candidate.is_symlink():
                raise ValueError(
                    f"Invalid context name '{name}': symbolic links are not "
                    "allowed in context namespaces."
                )
            if candidate.exists() and not candidate.is_dir():
                raise ValueError(
                    f"Invalid context name '{name}': namespace component "
                    f"'{candidate.name}' is not a directory."
                )
        contexts_root = CONTEXTS_DIR.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Invalid context name '{name}': path escapes the context store."
            )
        return path

    def _context_file(self, name: str) -> Path:
        return self._context_dir(name) / "context.json"

    def _checkpoints_dir(self, name: str) -> Path:
        path = self._context_dir(name) / "checkpoints"
        if path.is_symlink():
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' through a "
                "symbolic link."
            )
        contexts_root = CONTEXTS_DIR.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' outside the "
                "context store."
            )
        return path

    def context_exists(self, name: str) -> bool:
        try:
            context_file = self._context_file(name)
        except (OSError, TypeError, ValueError):
            return False
        return context_file.is_file() and not context_file.is_symlink()

    def list_context_names(self) -> list[str]:
        names: list[str] = []
        for context_file in CONTEXTS_DIR.rglob("context.json"):
            if not context_file.is_file() or context_file.is_symlink():
                continue
            name = context_file.parent.relative_to(CONTEXTS_DIR).as_posix()
            try:
                _context_name_parts(name)
            except ValueError:
                continue
            try:
                with open(context_file) as f:
                    data = json.load(f)
                _validate_context_header(data, name)
            except (OSError, json.JSONDecodeError):
                continue
            except ValueError:
                continue

            names.append(name)
        return sorted(names)

    def _assert_context_storage_available(self, name: str) -> None:
        """Allow a new root Context when only namespace directories predate it."""
        context_dir = self._context_dir(name)
        if not context_dir.exists():
            return
        invalid_entries = [
            entry.name
            for entry in context_dir.iterdir()
            if (
                entry.is_symlink()
                or not entry.is_dir()
                or entry.name.casefold() in RESERVED_CONTEXT_SEGMENTS
            )
        ]
        if invalid_entries:
            raise ValueError(
                f"Cannot create context '{name}': its storage directory already "
                "exists and is not empty; only child namespace directories may "
                "precede a root Context. Invalid entries: "
                + ", ".join(sorted(invalid_entries))
            )

    @staticmethod
    def _prune_empty_namespace_dirs(start: Path) -> None:
        """Remove empty namespace directories without removing CONTEXTS_DIR."""
        candidate = start
        while candidate != CONTEXTS_DIR:
            try:
                candidate.rmdir()
            except OSError:
                break
            candidate = candidate.parent

    # --- Load / Save ---

    def _load_direct_memory(
        self,
        context_name: str,
        expected_context_uid: str,
        memory_uid: str,
    ) -> Memory | None:
        """
        Resolve one directly owned Memory without recursively loading its Context.

        Reading the raw context file avoids MemoryRef chains and Context embed
        cycles. The Context uid check prevents a deleted/recreated context with
        the same name from silently becoming the new target.
        """
        if not self.context_exists(context_name):
            return None
        with open(self._context_file(context_name)) as f:
            data = json.load(f)
        try:
            data = _validate_context_header(data, context_name)
        except ValueError:
            return None
        if data.get("uid") != expected_context_uid:
            return None

        item = data.get("memories", {}).get(memory_uid)
        if (
            not isinstance(item, dict)
            or item.get("type") != "memory"
            or item.get("uid") != memory_uid
        ):
            return None
        return Memory.from_dict(item)

    def load(self, name: str, _loading: frozenset[str] = frozenset()) -> Context:
        """Load a context by name, resolving embedded context refs as live loads."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)

        def loader(ref_name: str) -> Context | None:
            if ref_name in _loading:
                return None  # break circular reference
            if not self.context_exists(ref_name):
                return None
            return self.load(ref_name, _loading | {name})

        try:
            return Context.from_dict(
                data,
                loader=loader,
                memory_loader=self._load_direct_memory,
            )
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_direct(self, name: str) -> Context:
        """
        Load one Context record without opening any referenced Context files.

        Read-only operations whose scope is explicitly limited to directly
        owned Memories must not resolve embedded Contexts or MemoryRef targets
        before filtering. QueryContextRefs remain opaque under both load paths.
        """
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        with open(self._context_file(name)) as f:
            data = json.load(f)
        data = _validate_context_header(data, name)
        try:
            return Context.from_dict(data)
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"Context file for '{name}' has an invalid memory structure: {e}"
            ) from e

    def load_current(self) -> Context:
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load(name)

    def load_current_direct(self) -> Context:
        """Load the current Context through the non-resolving direct path."""
        name = self.current_context_name()
        if not name:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        return self.load_direct(name)

    def save(self, ctx: Context, auto_checkpoint: Optional[AutoCheckpoint] = None) -> None:
        """Persist a context to disk. Caller is responsible for calling this after mutations."""
        ctx_dir = self._context_dir(ctx.name)
        context_file = self._context_file(ctx.name)
        if context_file.is_symlink():
            raise ValueError(
                f"Refusing to write context '{ctx.name}' through a symbolic link."
            )
        if not self.context_exists(ctx.name):
            self._assert_context_storage_available(ctx.name)
        ctx_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_dir(ctx.name).mkdir(parents=True, exist_ok=True)
        if auto_checkpoint is not None:
            self.checkpoint(
                ctx,
                message=auto_checkpoint.description,
                command=auto_checkpoint.command,
                args=auto_checkpoint.args,
                description=auto_checkpoint.description,
                auto=True,
                _allow_unsaved=True,
            )
        _write_json_atomic(context_file, ctx.to_dict())

    # --- Query-only research sources ---

    @staticmethod
    def _canonical_query_source_uid(source_uid: str) -> str:
        if not isinstance(source_uid, str):
            raise ValueError("Query source uid must be a canonical UUID.")
        try:
            parsed = uuid.UUID(source_uid)
        except (AttributeError, TypeError, ValueError) as e:
            raise ValueError("Query source uid must be a canonical UUID.") from e
        canonical = str(parsed)
        if source_uid != canonical:
            raise ValueError("Query source uid must be a canonical UUID.")
        return canonical

    def _query_source_dir(self, source_uid: str) -> Path:
        canonical = self._canonical_query_source_uid(source_uid)
        if QUERY_SOURCES_DIR.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        source_dir = QUERY_SOURCES_DIR / canonical
        if source_dir.is_symlink():
            raise ValueError("Query source directory cannot be a symbolic link.")
        root = QUERY_SOURCES_DIR.resolve()
        resolved = source_dir.resolve(strict=False)
        if root not in resolved.parents:
            raise ValueError("Query source path escapes query source storage.")
        return source_dir

    def _query_source_file(self, source_uid: str) -> Path:
        source_file = self._query_source_dir(source_uid) / "source.json"
        if source_file.is_symlink():
            raise ValueError("Query source file cannot be a symbolic link.")
        return source_file

    def create_query_source(self, name: str, content: str) -> QuerySource:
        """
        Store a concealed research source outside normal Context storage.

        This is UI-level concealment for a study prototype, not a security
        boundary. The local user can still read files under ~/.mem.
        """
        _context_name_parts(name)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Query source content must be non-empty text.")
        if QUERY_SOURCES_DIR.is_symlink():
            raise ValueError("Query source storage cannot be a symbolic link.")
        QUERY_SOURCES_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(QUERY_SOURCES_DIR, 0o700)

        source = QuerySource(uid=str(uuid.uuid4()), name=name, content=content)
        source_dir = self._query_source_dir(source.uid)
        source_file = self._query_source_file(source.uid)
        source_dir.mkdir(mode=0o700)
        os.chmod(source_dir, 0o700)
        try:
            with open(source_file, "x", encoding="utf-8") as f:
                json.dump(
                    {
                        "schema_version": 1,
                        "uid": source.uid,
                        "name": source.name,
                        "content": source.content,
                    },
                    f,
                    indent=2,
                )
            os.chmod(source_file, 0o600)
        except Exception:
            if source_file.exists() and not source_file.is_symlink():
                source_file.unlink()
            source_dir.rmdir()
            raise
        return source

    def load_query_source(
        self,
        source_uid: str,
        *,
        expected_name: str,
    ) -> QuerySource:
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f)
        if (
            not isinstance(data, dict)
            or data.get("schema_version") != 1
            or data.get("uid") != source_uid
            or data.get("name") != expected_name
            or not isinstance(data.get("content"), str)
        ):
            raise ValueError("Query source identity or structure is invalid.")
        return QuerySource(
            uid=data["uid"],
            name=data["name"],
            content=data["content"],
        )

    def delete_query_source(self, source_uid: str) -> None:
        """Delete one exact hidden source, used to roll back failed setup."""
        source_dir = self._query_source_dir(source_uid)
        source_file = self._query_source_file(source_uid)
        if not source_file.is_file():
            raise FileNotFoundError("Query source is unavailable.")
        source_file.unlink()
        source_dir.rmdir()

    def copy_checkpoints(self, source_name: str, target_name: str) -> None:
        """Copy all checkpoint files from source into target's checkpoints directory."""
        src_dir = self._checkpoints_dir(source_name)
        tgt_dir = self._checkpoints_dir(target_name)
        tgt_dir.mkdir(parents=True, exist_ok=True)
        if src_dir.exists():
            for path in sorted(src_dir.glob("*.json")):
                if path.is_symlink() or not path.is_file():
                    continue
                destination = tgt_dir / path.name
                if destination.is_symlink():
                    raise ValueError(
                        f"Refusing to copy checkpoint to '{target_name}' through "
                        "a symbolic link."
                    )
                shutil.copy2(path, destination)

    def delete(self, name: str) -> None:
        """Delete one Context while preserving descendant Context namespaces."""
        if not self.context_exists(name):
            raise FileNotFoundError(f"Context '{name}' not found.")
        ctx_dir = self._context_dir(name)
        context_file = self._context_file(name)
        checkpoints_dir = self._checkpoints_dir(name)
        if checkpoints_dir.exists() and not checkpoints_dir.is_dir():
            raise ValueError(
                f"Cannot delete context '{name}': its checkpoints path is not "
                "a directory."
            )

        # Move exact Context artifacts aside before deletion. Renames within a
        # directory are atomic, and descendants are never part of these paths.
        # If staging fails, restore the Context file before surfacing the error.
        token = uuid.uuid4().hex
        staged_context = ctx_dir / f".context.json.delete-{token}"
        staged_checkpoints = ctx_dir / f".checkpoints.delete-{token}"
        context_file.rename(staged_context)
        checkpoints_staged = False
        try:
            if checkpoints_dir.exists():
                checkpoints_dir.rename(staged_checkpoints)
                checkpoints_staged = True
        except OSError:
            staged_context.rename(context_file)
            raise

        try:
            staged_context.unlink()
        except OSError:
            if checkpoints_staged:
                staged_checkpoints.rename(checkpoints_dir)
            staged_context.rename(context_file)
            raise

        if self.current_context_name() == name:
            self._write_state({"current": None})
        if checkpoints_staged:
            shutil.rmtree(staged_checkpoints)
        self._prune_empty_namespace_dirs(ctx_dir)

    # --- Checkpoints ---

    # Storage design note:
    # Checkpoints intentionally embed a complete serialization of the Context's
    # direct state.  At the current research-prototype scale, this keeps
    # persistence, recovery, and migration simpler than an object store; nested
    # Contexts and MemoryRefs are already serialized as pointers rather than
    # recursively copied.  If Contexts or histories grow substantially, retain
    # the same logical snapshot semantics while moving Memory contents to
    # content-addressed blobs and having checkpoints point to ordered tree
    # manifests.  A pure delta/event chain is not required by the current model.
    def checkpoint(
        self,
        ctx: Context,
        message: str = "",
        command: Optional[str] = None,
        args: Optional[dict] = None,
        description: Optional[str] = None,
        auto: bool = False,
        _allow_unsaved: bool = False,
    ) -> Checkpoint:
        """Save a point-in-time snapshot of ctx's current state."""
        if not _allow_unsaved and not self.context_exists(ctx.name):
            raise FileNotFoundError(
                f"Context '{ctx.name}' must be saved before checkpointing."
            )
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
        cp_dir = self._checkpoints_dir(ctx.name)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"{ts}-{slug}-{cp.uid[:8]}.json"
        if cp_file.is_symlink():
            raise ValueError(
                f"Refusing to write checkpoint for '{ctx.name}' through a "
                "symbolic link."
            )
        _write_json_atomic(
            cp_file,
            {
                "uid": cp.uid,
                "message": cp.message,
                "timestamp": cp.timestamp.isoformat(),
                "snapshot": cp.snapshot,
                "command": cp.command,
                "args": cp.args,
                "description": cp.description,
                "auto": cp.auto,
            },
        )
        return cp

    def list_checkpoints(self, name: str) -> list[dict]:
        """Return checkpoints for a context, sorted newest-first."""
        cp_dir = self._checkpoints_dir(name)
        if not cp_dir.exists():
            return []
        entries = []
        for path in sorted(cp_dir.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
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
        cp_dir = self._checkpoints_dir(ctx_name)

        if not keep_history:
            log_snapshot = (target_data.get("args") or {}).get("log_snapshot")

            if log_snapshot is not None:
                # Target carries a log snapshot — fully restore the log from it
                for path in cp_dir.glob("*.json"):
                    if path.is_symlink() or path.is_file():
                        path.unlink()
                for entry in sorted(log_snapshot, key=lambda x: x["timestamp"]):
                    ts_file = datetime.fromisoformat(entry["timestamp"]).strftime("%Y%m%dT%H%M%S")
                    fname = f"{ts_file}-{entry['uid'][:8]}.json"
                    cp_file = cp_dir / fname
                    if cp_file.is_symlink():
                        raise ValueError(
                            f"Refusing to restore checkpoint for '{ctx_name}' "
                            "through a symbolic link."
                        )
                    with open(cp_file, "w") as f:
                        json.dump(entry, f, indent=2)
            else:
                # Simple truncation: remove checkpoints newer than target
                for path in cp_dir.glob("*.json"):
                    if path.is_symlink() or not path.is_file():
                        continue
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

        # A branch inherits checkpoint files whose snapshots still carry the
        # source Context identity. Restore their contents into the Context the
        # caller requested instead of writing back to the source Context.
        restored_snapshot = {
            **target_data["snapshot"],
            "uid": ctx.uid,
            "name": ctx.name,
        }
        restored = Context.from_dict(
            restored_snapshot,
            loader=loader,
            memory_loader=self._load_direct_memory,
        )
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
