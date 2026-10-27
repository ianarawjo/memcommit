"""Prepare project documents through shared Sync conversion before Profile setup."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from memcommit.application.operations.import_export_sync.common.conversion import (
    parse_project_documents,
)
from memcommit.application.operations.import_export_sync.common.model import (
    InputFile,
    MemContent,
)
from memcommit.application.operations.import_export_sync.common.native_store import (
    import_context_records,
)
from memcommit.persistence.store.attached_files import save_attached_file
from memcommit.persistence.import_export.source import read_project_documents


@dataclass(frozen=True)
class PreparedProjectImport:
    root: Path
    files: tuple[InputFile, ...]
    skipped_paths: tuple[str, ...]
    content: MemContent
    digest: str
    ignore_bytes: bytes | None = None


def prepare_project_import(root):
    root = Path(root).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"Project folder is not a directory: {root}")
    if root.exists():
        source = read_project_documents(root)
        files = tuple(
            InputFile(path=path, data=data)
            for path, data in source.files
        )
        skipped = ()
    else:
        files, skipped = (), ()
    content = parse_project_documents(files) if files else MemContent(contexts=())
    digest = sha256()
    ignore_bytes = source.ignore_bytes if root.exists() else None
    digest.update(b"ignore\0" + (ignore_bytes or b""))
    for file in files:
        digest.update(file.path.encode("utf-8") + b"\0" + sha256(file.data).digest())
    for path in skipped:
        digest.update(b"excluded\0" + path.encode("utf-8") + b"\0")
    return PreparedProjectImport(
        root=root,
        files=files,
        skipped_paths=skipped,
        content=content,
        digest=digest.hexdigest(),
        ignore_bytes=ignore_bytes,
    )


def import_project_documents(store, prepared):
    for digest, data in prepared.content.attached_data.items():
        if save_attached_file(store_root=store.store_dir, data=data) != digest:
            raise ValueError("Attached-file identity mismatch.")
    return import_context_records(
        store, ((context, None) for context in prepared.content.contexts)
    )


def verify_project_import_source(prepared):
    # Creation publishes only .mem; external edits must remain external edits.
    if (
        prepared.root.exists()
        and read_project_documents(prepared.root).ignore_bytes != prepared.ignore_bytes
    ):
        raise ValueError(
            "Project files changed during Profile setup; review creation again."
        )
    for file in prepared.files:
        path = prepared.root / file.path
        if path.is_symlink() or not path.is_file() or path.read_bytes() != file.data:
            raise ValueError(
                "Project files changed during Profile setup; review creation again."
            )
