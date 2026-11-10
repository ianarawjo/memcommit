"""Keep automatic Sync outside the command's own ledger and failure outcome."""

from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace

from memcommit.adapters.background.automatic_sync import ensure_worker
from memcommit.application.operations.import_export_sync.mem_sync.automatic.runtime import (
    AutomaticSyncOutcome,
    record_automatic_outcome,
    synchronize_automatically,
)
from memcommit.persistence.operations.mem_sync.automatic import (
    read_automatic_settings,
    sync_operation_lock,
    write_automatic_settings,
)
from memcommit.persistence.store import ProfileStore
from memcommit.persistence.store.infrastructure import paths


def _warn(message):
    from memcommit.adapters.console.terminal.core.output import echo_text

    echo_text("Automatic sync pending: {message}", message=message, err=True)


def _synchronize(store, trigger):
    try:
        outcome = synchronize_automatically(store, trigger=trigger)
        if outcome.message:
            _warn(outcome.message)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        _warn(str(error))


def _pause_before_command(store, settings):
    try:
        # Publish the pause before command code can change native content. A
        # failed final status write must leave the watcher unable to export it.
        record_automatic_outcome(
            store,
            AutomaticSyncOutcome(
                "paused",
                "A mem command is in progress or did not finish. Run a mem command or 'mem sync' to retry automatic synchronization.",
            ),
            trigger="COMMAND_START",
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        try:
            write_automatic_settings(store, False, profile_uid=settings.profile_uid)
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            RuntimeError,
        ) as disable_error:
            raise RuntimeError(
                "Automatic Sync could not be paused or disabled; the command was not started. "
                "Restore access to the Profile's Sync metadata and retry."
            ) from disable_error
        _warn(
            f"Automatic synchronization was disabled because its command pause could not be saved: {error}"
        )
        return False
    return True


@contextmanager
def automatic_sync_command():
    try:
        # Default-off scheduling must not open storage before ordinary command
        # parsing, including retired-option errors and read-only placeholders.
        selected_root = Path(paths.STORE_DIR)
        settings = read_automatic_settings(SimpleNamespace(store_dir=selected_root))
        enabled = settings.enabled
    except (OSError, ValueError, TypeError) as error:
        _warn(str(error))
        enabled = False
    if not enabled:
        yield
        return
    store = ProfileStore(root=selected_root, create=False)
    try:
        ensure_worker(store)
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        _warn(str(error))
    with ExitStack() as leases:
        try:
            leases.enter_context(sync_operation_lock(store))
        except (OSError, ValueError, TypeError, RuntimeError) as error:
            _warn(str(error))
            acquired = False
        else:
            acquired = True
        if not acquired:
            # Optional lease failures must not replace the command's outcome.
            # Yield outside the acquisition catch so body failures stay intact.
            yield
            return
        _synchronize(store, "COMMAND_START")
        if not _pause_before_command(store, settings):
            # Durable disablement permits the explicit command independently;
            # do not clear its failure boundary with another automatic attempt.
            yield
            return
        try:
            yield
        except BaseException as error:
            code = getattr(error, "exit_code", getattr(error, "code", None))
            if code == 0:
                _synchronize(store, "COMMAND_END")
            else:
                try:
                    # A failed operation may have published only part of its
                    # intended state. Resume on the next explicit mem action.
                    record_automatic_outcome(
                        store,
                        AutomaticSyncOutcome(
                            "paused",
                            "A mem command failed. Run a mem command or 'mem sync' to retry automatic synchronization.",
                        ),
                        trigger="COMMAND_FAILURE",
                    )
                except (OSError, ValueError, TypeError, KeyError, RuntimeError):
                    pass  # Do not replace the command's original failure.
            raise
        else:
            _synchronize(store, "COMMAND_END")
