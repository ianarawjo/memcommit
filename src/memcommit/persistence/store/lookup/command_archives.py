"""Find retained command archives without opening their JSON records."""

from pathlib import Path
import uuid


class _CommandArchiveLookupMixin:
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


    def list_command_context_archive_uids(self) -> tuple[str, ...]:
        root = self.command_context_archives_dir
        if not root.exists():
            if root.is_symlink():
                raise ValueError("Command Context archive storage is invalid.")
            return ()
        if root.is_symlink() or not root.is_dir():
            raise ValueError("Command Context archive storage is invalid.")
        checkpoint_uids: list[str] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_dir():
                raise ValueError("Command Context archive storage is invalid.")
            checkpoint_uids.append(path.name)
        return tuple(checkpoint_uids)
