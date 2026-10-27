"""Parse and render project-relative Markdown without transfer packages."""

from hashlib import sha256
from dataclasses import replace
from pathlib import PurePosixPath

from memcommit.core.context_name_validation import validate_context_name
from memcommit.core.document_path import relative_document_path
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)
from memcommit.persistence.store.context_hierarchy import (
    prepare_missing_ancestor_contexts,
)

from .formats import markdown
from .model import Document, MemContent, MemorySourceRange, OutputFile
from .spacing import SpacingPolicy


def validate_project_document_context_name(path):
    try:
        relative_document_path(path)
        for segment in PurePosixPath(path).parts:
            validate_context_name(segment)
        validate_context_name(PurePosixPath(path).with_suffix("").as_posix())
    except ValueError as error:
        raise ValueError(
            f"Invalid file or folder name in {path!r}; "
            "rename it to follow Context naming rules and retry."
        ) from error
    return path


def parse_document(text, *, path, state=None):
    if PurePosixPath(path).suffix.lower() != ".md":
        raise ValueError(f"Unsupported project document: {path}")
    return markdown.parse_markdown(text, path=path, state=state)


def parse_project_documents(files):
    contexts = {}
    for file in files:
        validate_project_document_context_name(file.path)
        try:
            text = file.data.decode("utf-8")
        except UnicodeError as error:
            raise ValueError(f"Expected UTF-8 document: {file.path}") from error
        document = parse_document(text, path=file.path)
        context = Context.create(PurePosixPath(file.path).with_suffix("").as_posix())
        for parent in prepare_missing_ancestor_contexts((context,), contexts):
            parent.corresponding_document_metadata = CorrespondingDocumentMetadata(
                parent.name, "md", role="directory"
            )
            contexts[parent.name] = parent
        name = context.name
        if name in contexts and (
            contexts[name].corresponding_document_metadata.role != "directory"
        ):
            raise ValueError(f"Project documents collide at Context: {name}")
        context.corresponding_document_metadata = document.state
        for block in document.blocks:
            context.add(Memory.create(block.text))
        contexts[name] = context
    return MemContent(tuple(contexts.values()))


def render_document(document, *, spacing_policy=SpacingPolicy(), source_ranges=None):
    return markdown.render_markdown(
        document, spacing_policy, source_ranges=source_ranges
    )


def normalize_document_bytes(data, *, path):
    """Normalize block separators, retaining syntax and block-internal bytes."""
    if data is None or PurePosixPath(path).suffix.lower() != ".md":
        return data
    return render_document(parse_document(data.decode("utf-8"), path=path)).encode(
        "utf-8"
    )


def render_context_documents(content, spacing_policy=SpacingPolicy()):
    files = []
    for context in content.contexts:
        state = context.corresponding_document_metadata
        if state is not None and state.role == "directory":
            if context.memories:
                raise ValueError(
                    f"Directory Context cannot contain document text: {context.name}"
                )
            continue
        if state is None:
            path = context.name + ".md"
            state = CorrespondingDocumentMetadata(path, "md")
        blocks = []
        for memory in context.iter_memories():
            for block in parse_document(
                memory.content, path=state.path, state=state
            ).blocks:
                blocks.append(
                    replace(
                        block,
                        source=MemorySourceRange(
                            context.uid,
                            context.name,
                            memory.uid,
                            block.start_byte,
                            block.end_byte,
                        ),
                    )
                )
        ranges = []
        text = render_document(
            Document(state, tuple(blocks)),
            spacing_policy=spacing_policy,
            source_ranges=ranges,
        )
        files.append(
            OutputFile(state.path, text.encode("utf-8"), source_ranges=tuple(ranges))
        )
        for asset in context.asset_metadata:
            data = content.attached_data.get(asset.sha256)
            if data is None or sha256(data).hexdigest() != asset.sha256:
                raise ValueError(f"Retained asset bytes are unavailable: {asset.path}")
            files.append(OutputFile(asset.path, data, attached=True))
    validate_output_files(files)
    return tuple(files)


def validate_output_files(files):
    paths = set()
    for file in files:
        relative_document_path(file.path)
        if file.path in paths:
            raise ValueError(f"Documents have the same output path: {file.path}")
        paths.add(file.path)
    for path in paths:
        if any(
            parent.as_posix() in paths
            for parent in PurePosixPath(path).parents
            if parent.as_posix() != "."
        ):
            raise ValueError(f"Document output collides with a directory: {path}")
