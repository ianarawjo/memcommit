"""Scan ordinary Context records into a validated catalog."""

from __future__ import annotations

import json
from pathlib import Path

from memcommit.core.context_targeting.context_catalog import (
    ContextCatalogDiagnostic,
    ContextCatalogDiagnosticCode,
    ContextCatalogScan,
)

from .records import _context_name_parts, _validate_context_header


class _ContextCatalogScanMixin:
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
                entries = tuple(sorted(directory.iterdir(), key=lambda entry: entry.name))
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
                                message="Context storage contains a symbolic-link entry.",
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
                                    message="Context record path is not a regular file.",
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
                                    message="Context storage contains a special entry.",
                                )
                            )
                        continue
                    if not entry.is_file():
                        diagnostics.append(
                            self._catalog_diagnostic(
                                "UNSAFE_ENTRY",
                                entry,
                                context_name=None,
                                message="Context record path is not a regular file.",
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

            # Reverse sorted children because ``pending`` is a LIFO stack.
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

    def list_context_names(self) -> list[str]:
        return list(self.scan_context_catalog().names)
