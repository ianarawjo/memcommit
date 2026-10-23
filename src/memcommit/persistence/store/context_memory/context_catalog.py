"""Find ordinary Context files and list their names."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from memcommit.core.context_name_validation import validate_context_name
from memcommit.core.context_targeting.resolution import sort_context_names


class _ContextCatalogStoreMixin:
    def scan_context_catalog(self) -> tuple[tuple[str, Path], ...]:
        """Return Context names and paths without opening their JSON records."""
        if not self._assert_context_storage_root():
            return ()

        records: list[tuple[str, Path]] = []
        pending = [self.contexts_dir]
        while pending:
            directory = pending.pop()
            child_directories: list[Path] = []
            for entry in sorted(directory.iterdir(), key=lambda entry: entry.name):
                # History snapshots must not become ordinary Context entries.
                if entry.name == "checkpoints":
                    continue
                if entry.is_symlink():
                    raise ValueError(
                        f"Context storage contains a symbolic-link entry: '{entry}'."
                    )
                if entry.is_dir():
                    if entry.name == "context.json":
                        raise ValueError(
                            f"Context record path is not a regular file: '{entry}'."
                        )
                    child_directories.append(entry)
                    continue
                if not entry.is_file():
                    raise ValueError(
                        f"Context storage contains a special entry: '{entry}'."
                    )
                if entry.name != "context.json":
                    continue

                name = entry.parent.relative_to(self.contexts_dir).as_posix()
                validate_context_name(name)
                records.append((name, entry))

            # Reverse sorted children because ``pending`` is a LIFO stack.
            pending.extend(reversed(child_directories))

        return tuple(sorted(records))

    def list_context_names(
        self,
        *,
        sort_order: Literal["hierarchical", "alphabetical"] = "hierarchical",
    ) -> list[str]:
        names = [name for name, _path in self.scan_context_catalog()]
        return list(sort_context_names(names, sort_order=sort_order))
