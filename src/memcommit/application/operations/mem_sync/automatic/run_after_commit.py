"""Run automatic Sync once at a completed application boundary, never inside save."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from memcommit.application.operations.mem_sync.model import SyncRequest, SyncResult
from .settings import automatic_sync_enabled


_completion_depth = ContextVar("mem_sync_completion_depth", default=0)
_sync_running = ContextVar("mem_sync_running", default=False)
_active_completion = ContextVar("mem_sync_active_completion", default=None)


def run_automatic_sync_after_commit(store=None, *, causing_command=None):
    if _sync_running.get():
        return ()
    from memcommit.persistence.store import MemoryStore
    from memcommit.persistence.operations.mem_sync.settings_repository import (
        SyncSettingsRepository,
    )
    from memcommit.application.operations.mem_sync.runtime import SyncRuntime
    from memcommit.application.operations.mem_sync.application import run_sync

    store = store or MemoryStore(create=False)
    repository = SyncSettingsRepository(store)
    names = ()
    token = _sync_running.set(True)
    try:
        settings = repository.load()
        if not any(rule["enabled"] for rule in settings["policies"]):
            return ()
        contexts = store.load_direct_context_graph_strict()
        inventory = {context.name: context.uid for context in contexts}
        names = tuple(
            sorted(
                context.name
                for context in contexts
                if automatic_sync_enabled(
                    context.name, context.uid, settings["policies"], inventory
                )
            )
        )
        runtime = SyncRuntime(store)
        result = run_sync(
            SyncRequest(
                selected_names=names, automatic=True, causing_command=causing_command
            ),
            runtime,
        )
        if result.run_uid is None:
            return ()
        return (result,)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        # A failed external write cannot roll back or report failure of the
        # already committed primary Memory operation. Retry Sync alone.
        try:
            settings = repository.load()
            repository.save(
                {
                    **settings,
                    "errors": {
                        **settings["errors"],
                        **dict.fromkeys(names, str(error)),
                    },
                },
                expected_revision=settings["revision"],
            )
        except (OSError, ValueError, RuntimeError):
            pass
        return (SyncResult(names, automatic=True, error=str(error)),)
    finally:
        _sync_running.reset(token)


@dataclass
class AutomaticSyncCompletion:
    store: object | None = None
    results: tuple[SyncResult, ...] = field(default_factory=tuple)


def register_default_store_for_completion(store):
    """Capture the first operation Store without opening storage for a parser."""
    completion = _active_completion.get()
    if completion is not None and completion.store is None and not _sync_running.get():
        completion.store = store


@contextmanager
def automatic_sync_completion(store=None, *, causing_command=None):
    """Coalesce nested application calls; adapters only render returned facts.

    Embedding callers use this around their complete operation, after which all
    Context/checkpoint transactions and their locks have left scope. CLI root
    wiring supplies the same boundary for existing command-owned operations.
    """
    outermost = _completion_depth.get() == 0
    token = _completion_depth.set(_completion_depth.get() + 1)
    completion = AutomaticSyncCompletion(store=store)
    frame_token = _active_completion.set(completion) if outermost else None
    if not outermost and store is not None:
        register_default_store_for_completion(store)
    completed = False
    try:
        yield completion
        completed = True
    except BaseException as error:
        completed = getattr(error, "exit_code", None) == 0 or (
            isinstance(error, SystemExit) and error.code == 0
        )
        raise
    finally:
        _completion_depth.reset(token)
        if frame_token is not None:
            _active_completion.reset(frame_token)
        if completed and outermost and completion.store is not None:
            completion.results = run_automatic_sync_after_commit(
                completion.store, causing_command=causing_command
            )
