"""Freeze project documents before publishing a new Profile."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from memcommit.application.capabilities.import_export.conversion import (
    convert_for_import,
)
from memcommit.application.capabilities.import_export.model import InputFile, MemContent
from memcommit.application.operations.mem_import.application import ImportRequest
from memcommit.application.operations.mem_import.documents.publication import (
    publish_document_import,
)
from memcommit.persistence.import_export.source import read_source


@dataclass(frozen=True)
class PreparedProjectImport:
    root: Path
    files: tuple[InputFile, ...]
    skipped_paths: tuple[str, ...]
    content: MemContent
    digest: str


def prepare_project_import(root):
    root = Path(root).expanduser().resolve()
    if root.exists() and not root.is_dir():
        raise ValueError(f"Project folder is not a directory: {root}")
    if root.exists():
        source = read_source(root, recursive=True)
        files = tuple(
            InputFile(path, data)
            for path, data in source.files
            if Path(path).suffix.lower() in {".md", ".txt", ".yaml", ".yml"}
        )
        skipped = tuple(
            sorted(
                (
                    *source.skipped,
                    *(
                        path
                        for path, _ in source.files
                        if Path(path).suffix.lower()
                        not in {".md", ".txt", ".yaml", ".yml"}
                    ),
                )
            )
        )
    else:
        files, skipped = (), ()
    content = (
        convert_for_import(files, "documents", None)[0] if files else MemContent(())
    )
    digest = sha256()
    for file in files:
        digest.update(file.path.encode("utf-8") + b"\0" + sha256(file.data).digest())
    for path in skipped:
        digest.update(b"excluded\0" + path.encode("utf-8") + b"\0")
    return PreparedProjectImport(root, files, skipped, content, digest.hexdigest())


def import_project_documents(store, prepared):
    return publish_document_import(
        store,
        ImportRequest(prepared.root, format="documents", recursive=True),
        prepared.content,
    )


def verify_project_import_source(prepared):
    # Creation publishes only .mem; external edits must remain external edits.
    for file in prepared.files:
        path = prepared.root / file.path
        if path.is_symlink() or not path.is_file() or path.read_bytes() != file.data:
            raise ValueError(
                "Project files changed during Profile setup; review creation again."
            )
