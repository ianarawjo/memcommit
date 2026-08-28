"""Discover and validate ordinary Context record paths."""

from __future__ import annotations

import json
from pathlib import Path

from memcommit.core.context_targeting.naming import (
    RESERVED_CONTEXT_SEGMENTS,
    validate_portable_context_name,
)
from memcommit.core.context_targeting.context_catalog import (
    ContextCatalogDiagnostic,
    ContextCatalogDiagnosticCode,
    ContextCatalogScan,
)

from .records import (
    _context_name_parts,
    _validate_context_header,
)


class _ContextDiscoveryMixin:
    def _assert_context_storage_root(self) -> bool:
        """Return whether the ordinary root exists, rejecting unsafe aliases.

        A symlink at ``contexts/`` used to bypass the per-namespace symlink
        checks because every descendant resolved inside the aliased root.  All
        ordinary Context paths enter through this guard so a catalog read and a
        later load/write enforce the same storage boundary.
        """
        if self.contexts_dir.is_symlink():
            raise ValueError("Context storage root cannot be a symbolic link.")
        if not self.contexts_dir.exists():
            return False
        if not self.contexts_dir.is_dir():
            raise ValueError("Context storage root is not a directory.")
        return True

    def _catalog_diagnostic(
        self,
        code: ContextCatalogDiagnosticCode,
        path: Path,
        *,
        context_name: str | None,
        message: str,
    ) -> ContextCatalogDiagnostic:
        try:
            relative_path = path.relative_to(self.contexts_dir).as_posix()
        except ValueError:
            relative_path = str(path)
        return ContextCatalogDiagnostic(
            code=code,
            relative_path=relative_path or ".",
            context_name=context_name,
            message=message,
        )

    def _scan_context_record_paths(
        self,
    ) -> tuple[
        tuple[tuple[str, Path], ...],
        tuple[ContextCatalogDiagnostic, ...],
    ]:
        """Discover ordinary record paths without following namespace links."""
        if not self._assert_context_storage_root():
            return (), ()

        records: list[tuple[str, Path]] = []
        diagnostics: list[ContextCatalogDiagnostic] = []
        pending = [self.contexts_dir]
        while pending:
            directory = pending.pop()
            try:
                entries = tuple(
                    sorted(directory.iterdir(), key=lambda entry: entry.name)
                )
            except OSError as error:
                diagnostics.append(
                    self._catalog_diagnostic(
                        "UNREADABLE_ENTRY",
                        directory,
                        context_name=None,
                        message=f"Context namespace could not be read: {error}",
                    )
                )
                continue

            child_directories: list[Path] = []
            for entry in entries:
                # Checkpoint snapshots are history, not ordinary Contexts. Their
                # own readers retain the stricter checkpoint-specific boundary.
                if entry.name == "checkpoints":
                    continue
                try:
                    if entry.is_symlink():
                        diagnostics.append(
                            self._catalog_diagnostic(
                                "UNSAFE_ENTRY",
                                entry,
                                context_name=None,
                                message=(
                                    "Context storage contains a symbolic-link entry."
                                ),
                            )
                        )
                        continue
                    if entry.is_dir():
                        if entry.name == "context.json":
                            diagnostics.append(
                                self._catalog_diagnostic(
                                    "UNSAFE_ENTRY",
                                    entry,
                                    context_name=None,
                                    message=(
                                        "Context record path is not a regular file."
                                    ),
                                )
                            )
                        else:
                            child_directories.append(entry)
                        continue
                    if entry.name != "context.json":
                        if not entry.is_file():
                            diagnostics.append(
                                self._catalog_diagnostic(
                                    "UNSAFE_ENTRY",
                                    entry,
                                    context_name=None,
                                    message=(
                                        "Context storage contains a special entry."
                                    ),
                                )
                            )
                        continue
                    if not entry.is_file():
                        diagnostics.append(
                            self._catalog_diagnostic(
                                "UNSAFE_ENTRY",
                                entry,
                                context_name=None,
                                message=("Context record path is not a regular file."),
                            )
                        )
                        continue
                except OSError as error:
                    diagnostics.append(
                        self._catalog_diagnostic(
                            "UNREADABLE_ENTRY",
                            entry,
                            context_name=None,
                            message=f"Context storage entry is unreadable: {error}",
                        )
                    )
                    continue

                name = entry.parent.relative_to(self.contexts_dir).as_posix()
                try:
                    _context_name_parts(name)
                except ValueError as error:
                    diagnostics.append(
                        self._catalog_diagnostic(
                            "INVALID_LOCATOR",
                            entry,
                            context_name=name,
                            message=str(error),
                        )
                    )
                    continue
                records.append((name, entry))

            # Reverse the sorted children because ``pending`` is a LIFO stack.
            pending.extend(reversed(child_directories))

        return tuple(sorted(records)), tuple(diagnostics)

    def scan_context_catalog(self) -> ContextCatalogScan:
        """Return header-valid ordinary names and typed omission diagnostics."""
        records, diagnostics = self._scan_context_record_paths()
        names: list[str] = []
        found_diagnostics = list(diagnostics)
        for name, context_file in records:
            try:
                with open(context_file, encoding="utf-8") as file:
                    data = json.load(file)
            except OSError as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "UNREADABLE_ENTRY",
                        context_file,
                        context_name=name,
                        message=f"Context record could not be read: {error}",
                    )
                )
                continue
            except (UnicodeError, json.JSONDecodeError) as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "INVALID_JSON",
                        context_file,
                        context_name=name,
                        message=f"Context record is invalid JSON: {error}",
                    )
                )
                continue
            try:
                _validate_context_header(data, name)
            except ValueError as error:
                found_diagnostics.append(
                    self._catalog_diagnostic(
                        "INVALID_HEADER",
                        context_file,
                        context_name=name,
                        message=str(error),
                    )
                )
                continue
            names.append(name)
        return ContextCatalogScan(
            names=tuple(sorted(names)),
            diagnostics=tuple(found_diagnostics),
        )

    def _context_dir(self, name: str) -> Path:
        self._assert_context_storage_root()
        parts = _context_name_parts(name)
        path = self.contexts_dir.joinpath(*parts)
        candidate = self.contexts_dir
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
        contexts_root = self.contexts_dir.resolve()
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
                f"Refusing to access checkpoints for '{name}' through a symbolic link."
            )
        contexts_root = self.contexts_dir.resolve()
        resolved = path.resolve(strict=False)
        if resolved != contexts_root and contexts_root not in resolved.parents:
            raise ValueError(
                f"Refusing to access checkpoints for '{name}' outside the "
                "context store."
            )
        return path

    def context_exists(self, name: str) -> bool:
        if not self._assert_context_storage_root():
            return False
        try:
            context_file = self._context_file(name)
        except (OSError, TypeError, ValueError):
            return False
        return context_file.is_file() and not context_file.is_symlink()

    def list_context_names(self) -> list[str]:
        return list(self.scan_context_catalog().names)

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

    def _prune_empty_namespace_dirs(self, start: Path) -> None:
        """Remove empty namespace directories without removing self.contexts_dir."""
        candidate = start
        while candidate != self.contexts_dir:
            try:
                candidate.rmdir()
            except OSError:
                break
            candidate = candidate.parent

    def assert_context_creatable(self, name: str) -> None:
        """Fail before expensive work when a new Context cannot use this name."""
        validate_portable_context_name(name)
        if self.context_exists(name):
            raise FileExistsError(f"Context '{name}' already exists.")
        self._assert_context_storage_available(name)
