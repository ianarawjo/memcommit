"""Prepare companion operation sessions coupled to command restoration."""

from __future__ import annotations
from pathlib import Path
from ...context_memory.models import ConcurrentContextUpdateError


class _CompanionSessionRestorationMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _prepare_sever_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Sever-session half of one self-save restoration."""

        if unit.command != "sever" or not unit.changes:
            return None
        if any(
            change.before is None or change.after is None for change in unit.changes
        ):
            # Other-save creation uses the dedicated lifecycle restoration.
            return None
        records: list[tuple[dict[str, object], dict[str, object]]] = []
        for change in unit.changes:
            checkpoint = next(
                (
                    entry
                    for entry in self.list_checkpoints(change.context_name)
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
            record = args.get("sever") if isinstance(args, dict) else None
            if not isinstance(args, dict) or not isinstance(record, dict):
                raise ValueError(
                    "In-place Sever checkpoint has no valid session receipt."
                )
            records.append((args, record))
        session_uids = {record.get("session_uid") for _args, record in records}
        sources = {record.get("source") for _args, record in records}
        outputs = {record.get("output") for _args, record in records}
        save_modes = {record.get("save_mode") for _args, record in records}
        if (
            len(session_uids) != 1
            or not all(isinstance(item, str) and item for item in session_uids)
            or len(sources) != 1
            or sources != outputs
            or save_modes != {"SELF_SAVE"}
            or any(record != records[0][1] for _args, record in records[1:])
        ):
            raise ValueError(
                "In-place Sever checkpoint session receipts are inconsistent."
            )
        session_uid = next(iter(session_uids))
        source_name = next(iter(sources))
        assert isinstance(session_uid, str)
        assert isinstance(source_name, str)
        from memcommit.application.operations.sever.model import SeverApplication
        from memcommit.application.operations.sever.model import (
            SeverCheckpointReceipt,
        )
        from memcommit.application.operations.sever.session_store import (
            SeverSessionStore,
        )

        sessions = SeverSessionStore(self)
        session = sessions.load(session_uid)
        result_uids = tuple(
            source.uid for _candidate, source, _content in session.results()
        )
        checkpoint_by_identity = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        receipts = tuple(
            SeverCheckpointReceipt(
                context_uid=context_uid,
                context_name=context_name,
                checkpoint_uid=checkpoint_by_identity[(context_uid, context_name)],
            )
            for context_name, context_uid, _digest in session.source.contexts
            if (context_uid, context_name) in checkpoint_by_identity
        )
        if len(receipts) != len(unit.changes):
            raise ValueError(
                "In-place Sever checkpoints are outside the frozen Source scope."
            )
        has_owner_membership = any(
            isinstance(args.get("command_contexts"), list) for args, _record in records
        )
        if len(receipts) > 1 and not has_owner_membership:
            raise ValueError(
                "Recursive in-place Sever checkpoints have no command membership."
            )
        application = SeverApplication(
            output_context_uid=receipts[0].context_uid,
            checkpoint_uid=receipts[0].checkpoint_uid,
            result_memory_uids=result_uids,
            checkpoints=receipts if has_owner_membership else (),
        )
        if (
            session.save_mode != "SELF_SAVE"
            or session.output_name != source_name
            or session.source.root_uid != receipts[0].context_uid
        ):
            raise ValueError("In-place Sever session does not match its command.")
        if direction == "undo":
            if session.state != "APPLIED" or session.application != application:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Undo."
                )
            restored = session.clear_application(
                output_context_uid=application.output_context_uid,
                checkpoint_uid=application.checkpoint_uid,
            )
        else:
            if session.state != "REVIEWING" or session.application is not None:
                raise ConcurrentContextUpdateError(
                    "The self-save Sever session changed before Redo."
                )
            restored = session.with_application(application)
        return sessions._path(session.uid), session.to_dict(), restored.to_dict()

    def _prepare_meld_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the Meld-session half of one Context command restoration."""
        if unit.command != "meld":
            return None
        if not unit.changes:
            raise ValueError("A Meld command has no target Context changes.")
        records: list[dict[str, object]] = []
        for change in unit.changes:
            checkpoint = next(
                (
                    entry
                    for entry in self.list_checkpoints(change.context_name)
                    if entry.get("uid") == change.checkpoint_uid
                ),
                None,
            )
            args = checkpoint.get("args") if isinstance(checkpoint, dict) else None
            record = args.get("meld") if isinstance(args, dict) else None
            if not isinstance(record, dict):
                raise ValueError("Meld checkpoint has no valid session receipt.")
            records.append(record)
        session_uids = {record.get("session_uid") for record in records}
        change_set_digests = {record.get("change_set_digest") for record in records}
        raw_results = records[0].get("results")
        if (
            len(session_uids) != 1
            or len(change_set_digests) != 1
            or not all(isinstance(item, str) and item for item in session_uids)
            or not all(isinstance(item, str) and item for item in change_set_digests)
            or not isinstance(raw_results, list)
            or any(record.get("results") != raw_results for record in records[1:])
        ):
            raise ValueError("Meld checkpoint session receipts are inconsistent.")
        session_uid = next(iter(session_uids))
        change_set_digest = next(iter(change_set_digests))
        result_uids = tuple(
            result.get("memory_uid")
            for result in raw_results
            if isinstance(result, dict) and isinstance(result.get("memory_uid"), str)
        )
        if len(result_uids) != len(raw_results):
            raise ValueError("Meld checkpoint result identities are invalid.")
        target = records[0].get("target_baseline")
        if not isinstance(target, dict):
            raise ValueError("Meld checkpoint target binding is invalid.")
        target_uid = target.get("context_uid")
        target_name = target.get("context_name")
        if not isinstance(target_uid, str) or not isinstance(target_name, str):
            raise ValueError("Meld checkpoint target binding is invalid.")
        session = self.load_meld_session(target_uid)
        if (
            session is None
            or session.uid != session_uid
            or session.target.context_uid != target_uid
            or session.target.context_name != target_name
        ):
            raise ValueError("Meld session does not match the restored command.")
        from memcommit.application.operations.meld.model import (
            MELD_OWNER_AWARE_SCHEMA_VERSION,
            MeldCheckpointReceipt,
        )

        checkpoint_by_identity = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        baseline = session.frames[1]
        owner_order = (
            tuple((context.uid, context.name) for context in baseline.contexts)
            if baseline.contexts is not None
            else ((target_uid, target_name),)
        )
        receipts = tuple(
            MeldCheckpointReceipt(
                context_uid=context_uid,
                context_name=context_name,
                checkpoint_uid=checkpoint_by_identity[(context_uid, context_name)],
            )
            for context_uid, context_name in owner_order
            if (context_uid, context_name) in checkpoint_by_identity
        )
        if len(receipts) != len(unit.changes):
            raise ValueError("Meld checkpoint owners are outside the target scope.")
        primary_checkpoint_uid = receipts[0].checkpoint_uid
        application_receipts = (
            receipts
            if session.schema_version >= MELD_OWNER_AWARE_SCHEMA_VERSION
            else ()
        )
        before = session.to_dict()
        if direction == "undo":
            session.clear_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                checkpoints=application_receipts,
            )
        elif session.state == "READY_TO_APPLY" and session.application is None:
            session.record_application(
                change_set_digest=change_set_digest,
                checkpoint_uid=primary_checkpoint_uid,
                result_memory_uids=result_uids,
                checkpoints=application_receipts,
            )
        elif not (
            session.state == "APPLIED"
            and session.application is not None
            and session.application.change_set_digest == change_set_digest
            and session.application.checkpoint_uid == primary_checkpoint_uid
            and session.application.result_memory_uids == result_uids
            and (
                not session.application.checkpoints
                or session.application.checkpoints == receipts
            )
        ):
            raise ValueError("Meld session cannot be restored to applied state.")
        return self._meld_session_path(target_uid), before, session.to_dict()

    def _prepare_update_command_restore(
        self,
        unit,
        direction: str,
    ) -> tuple[Path, dict[str, object], dict[str, object]] | None:
        """Prepare the active local Update receipt coupled to its checkpoints."""
        from memcommit.application.operations.update.model import operation_digest

        session = self.load_staged_update()
        if session is None:
            # Granted-target Contexts live in the authority Profile; their
            # participant receipt is coordinated by restore_update_command.
            return None
        digest = operation_digest(session.operations)
        expected_unit_uid = f"update:{session.uid}:{digest}"
        if unit.uid != expected_unit_uid:
            return None
        if session.application is None:
            raise ValueError("Update command has no application receipt.")
        receipt_by_context = {
            (receipt.context_uid, receipt.context_name): receipt.checkpoint_uid
            for receipt in session.application.checkpoints
        }
        command_by_context = {
            (change.context_uid, change.context_name): change.checkpoint_uid
            for change in unit.changes
        }
        if (
            session.application.operation_digest != digest
            or receipt_by_context != command_by_context
        ):
            raise ValueError("Update application receipt does not match this command.")
        before = session.to_dict()
        if direction == "undo":
            session = session.with_restored_application(applied=False)
        elif session.status == "undone":
            session = session.with_restored_application(applied=True)
        elif session.status != "applied":
            raise ValueError("Update session cannot be restored to applied state.")
        return self.staged_update_file, before, session.to_dict()
