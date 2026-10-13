"""Shared document preparation and exact external publication for Export and Sync."""

from hashlib import sha256
from pathlib import Path
from typing import Protocol

from .conversion import convert_for_export, validate_output_files
from .model import ExportFileEffect, ExportPlan, MemContent, OutputFile


class ExportPublicationPort(Protocol):
    def publish(self, plan: ExportPlan) -> None: ...


def prepare_export_documents(content: MemContent, format=None, **options):
    return convert_for_export(content, format, **options)


def plan_export_documents(
    destination: Path,
    files: tuple[OutputFile, ...],
    previous_files: dict[str, bytes | None],
    *,
    removals: tuple[str, ...] = (),
    directories: tuple[str, ...] = (),
    removed_directories: tuple[str, ...] = (),
) -> ExportPlan:
    validate_output_files(files)
    file_paths = {file.path for file in files}
    if file_paths.intersection(removals):
        raise ValueError("An Export path cannot be both written and removed.")
    expected = file_paths | set(removals)
    if not expected.issubset(previous_files):
        raise ValueError("Export plan lacks an exact external preimage.")
    effects = tuple(
        ExportFileEffect(
            file.path,
            "UNCHANGED"
            if previous_files[file.path] == file.data
            else "ADD"
            if previous_files[file.path] is None
            else "EDIT",
            file.attached,
        )
        for file in files
    ) + tuple(ExportFileEffect(path, "REMOVE") for path in removals)
    return ExportPlan(
        Path(destination).absolute(),
        files,
        removals,
        directories,
        tuple(
            (
                path,
                sha256(previous_files[path]).hexdigest()
                if previous_files[path] is not None
                else None,
            )
            for path in sorted(expected)
        ),
        effects,
        removed_directories,
    )


def publish_export_documents(plan: ExportPlan, port: ExportPublicationPort):
    port.publish(plan)
    return plan.effects
