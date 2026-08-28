"""Retain exact Context creation records for later Redo."""

from __future__ import annotations
import json
import uuid
from pathlib import Path
from memcommit.core.context import Context
from ..context_memory.records import (
    _context_name_parts,
    _validate_context_header,
)
from ..infrastructure.atomic_io import (
    _reject_duplicate_json_keys,
)


class _CommandArchiveMixin:
    """Focused slice of checkpoint or command restoration persistence."""

    def _command_context_archive_path(self, checkpoint_uid: str) -> Path:
        """Resolve one exact creation-command archive without accepting paths."""
        try:
            canonical = str(uuid.UUID(checkpoint_uid))
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Command archive checkpoint uid is invalid.") from error
        if canonical != checkpoint_uid:
            raise ValueError("Command archive checkpoint uid is invalid.")
        root = self.command_context_archives_dir
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise ValueError("Command Context archive storage is invalid.")
        return root / checkpoint_uid

    def _load_command_context_archive(
        self,
        checkpoint_uid: str,
    ) -> tuple[Path, dict[str, object], Context, list[dict[str, object]]]:
        """Load one absent Context and its retained checkpoint history."""
        archive = self._command_context_archive_path(checkpoint_uid)
        if archive.is_symlink() or not archive.is_dir():
            raise FileNotFoundError("Command Context archive is unavailable.")
        manifest_path = archive / "manifest.json"
        context_path = archive / "context.json"
        checkpoints_path = archive / "checkpoints"
        for path, label in (
            (manifest_path, "manifest"),
            (context_path, "Context record"),
        ):
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"Command Context archive {label} is invalid.")
        if checkpoints_path.is_symlink() or not checkpoints_path.is_dir():
            raise ValueError("Command Context archive checkpoints are invalid.")
        with open(manifest_path, encoding="utf-8") as file:
            manifest = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        sever_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "session_uid",
            "application",
            "reviewing_session_digest",
        }
        lifecycle_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
        }
        atomize_manifest_fields = {
            "version",
            "command",
            "unit_uid",
            "context_uid",
            "context_name",
            "checkpoint_uid",
            "analysis_uid",
            "source_context_uid",
            "source_context_name",
            "source_workbench",
            "reviewing_workbench_digest",
            "terminal_workbench_digest",
            "current_before",
        }
        if (
            not isinstance(manifest, dict)
            or manifest.get("version") != 1
            or manifest.get("checkpoint_uid") != checkpoint_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        command = manifest.get("command")
        unit_uid = manifest.get("unit_uid")
        if command == "sever":
            if (
                set(manifest) != sever_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "merge":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("merge:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "branch":
            if (
                set(manifest) != lifecycle_manifest_fields
                or not isinstance(unit_uid, str)
                or not unit_uid.startswith("branch:")
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            if (
                set(manifest) != atomize_manifest_fields
                or unit_uid != f"checkpoint:{checkpoint_uid}"
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        else:
            raise ValueError("Command Context archive manifest is invalid.")
        context_name = manifest.get("context_name")
        context_uid = manifest.get("context_uid")
        if (
            not isinstance(context_name, str)
            or not context_name
            or not isinstance(context_uid, str)
            or not context_uid
        ):
            raise ValueError("Command Context archive manifest is invalid.")
        if command == "sever":
            session_uid = manifest.get("session_uid")
            reviewing_digest = manifest.get("reviewing_session_digest")
            if (
                not isinstance(session_uid, str)
                or not session_uid
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in reviewing_digest
                )
                or not isinstance(manifest.get("application"), dict)
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        elif command == "atomize":
            source_context_uid = manifest.get("source_context_uid")
            source_context_name = manifest.get("source_context_name")
            analysis_uid = manifest.get("analysis_uid")
            current_before = manifest.get("current_before")
            if (
                not isinstance(source_context_uid, str)
                or not source_context_uid
                or not isinstance(source_context_name, str)
                or not source_context_name
                or not isinstance(analysis_uid, str)
                or not analysis_uid
                or (current_before is not None and not isinstance(current_before, str))
            ):
                raise ValueError("Command Context archive manifest is invalid.")
            _context_name_parts(source_context_name)
            source_workbench = manifest.get("source_workbench")
            reviewing_digest = manifest.get("reviewing_workbench_digest")
            terminal_digest = manifest.get("terminal_workbench_digest")
            if source_workbench is None:
                if reviewing_digest is not None or terminal_digest is not None:
                    raise ValueError("Command Context archive manifest is invalid.")
            elif (
                not isinstance(source_workbench, dict)
                or not isinstance(reviewing_digest, str)
                or len(reviewing_digest) != 64
                or not isinstance(terminal_digest, str)
                or len(terminal_digest) != 64
            ):
                raise ValueError("Command Context archive manifest is invalid.")
        _context_name_parts(context_name)
        with open(context_path, encoding="utf-8") as file:
            context_record = json.load(
                file,
                object_pairs_hook=_reject_duplicate_json_keys,
            )
        context = Context.from_dict(
            _validate_context_header(context_record, context_name)
        )
        if context.uid != context_uid:
            raise ValueError("Command Context archive identity is invalid.")
        entries: list[dict[str, object]] = []
        for path in checkpoints_path.iterdir():
            if path.is_symlink() or not path.is_file() or path.suffix != ".json":
                raise ValueError("Command Context archive checkpoints are invalid.")
            with open(path, encoding="utf-8") as file:
                value = json.load(
                    file,
                    object_pairs_hook=_reject_duplicate_json_keys,
                )
            if not isinstance(value, dict):
                raise ValueError("Command Context archive checkpoint is invalid.")
            entries.append(value)
        if not any(entry.get("uid") == checkpoint_uid for entry in entries):
            raise ValueError("Command Context archive lost its source checkpoint.")
        return (
            archive,
            manifest,
            context,
            sorted(entries, key=lambda item: str(item.get("timestamp")), reverse=True),
        )

    def list_command_context_archives(
        self,
    ) -> tuple[tuple[Context, list[dict[str, object]]], ...]:
        """Return validated absent Context histories used by command Undo/Redo."""
        root = self.command_context_archives_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Command Context archive storage is invalid.")
            return ()
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Command Context archive storage is invalid.")
        result: list[tuple[Context, list[dict[str, object]]]] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            _archive, _manifest, context, entries = self._load_command_context_archive(
                path.name
            )
            result.append((context, entries))
        return tuple(sorted(result, key=lambda item: item[0].name))
