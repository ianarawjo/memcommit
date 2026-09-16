"""Deterministic document composition with no Store, filesystem, or provider I/O."""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath
import hashlib
import posixpath
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

from memcommit.core.context import Context, Memory
from memcommit.core.document import AttachedFile, DocumentState, relative_document_path
from memcommit.core.context_targeting.naming import validate_portable_context_name
from .model import (
    ConversionIssue,
    Document,
    DocumentPackage,
    MemContent,
    OutputFile,
    PackageFormat,
    fail,
)
from .spacing import SpacingPolicy
from .formats import markdown, plain_text, yaml, skill, mem


_EXTENSIONS = {".md": "md", ".txt": "txt", ".yaml": "yaml", ".yml": "yaml"}
_ALIASES = {"markdown": "md", "text": "txt", "yml": "yaml", "auto": None}


def detect_format(files, format_hint=None):
    hint = _ALIASES.get(format_hint, format_hint)
    if hint is not None:
        if hint not in {"md", "txt", "yaml", "skill", "mem", "documents"}:
            fail("unsupported-format", "input", f"Unsupported format: {hint}")
        return hint
    if any(file.path == "SKILL.md" for file in files):
        return "skill"
    if files and all(
        file.path.endswith("context.json") or file.path.startswith("attached-files/")
        for file in files
    ):
        return "mem"
    return "documents"


def _segment(name):
    try:
        validate_portable_context_name(name)
        return name
    except ValueError:
        return "file-" + name.encode("utf-8").hex()


def _parse(text, format, path, state=None):
    parser = {
        "md": markdown.parse_markdown,
        "txt": plain_text.parse_text,
        "yaml": yaml.parse_yaml,
    }[format]
    return parser(text, path=path, state=state)


def convert_for_import(files, format, placement, *, single_file=False):
    files = tuple(files)
    format = detect_format(files, format)
    if format == "mem":
        return mem.decode_mem(files), ()
    documents = []
    attachments = []
    issues = []
    if format == "skill":
        documents.extend(skill.parse_skill(files).documents)
    for file in files:
        relative_document_path(file.path)
        if format == "skill" and file.path == "SKILL.md":
            continue
        extension = PurePosixPath(file.path).suffix.lower()
        file_format = _EXTENSIONS.get(extension)
        if file_format is None:
            if format == "skill":
                attachments.append(file)
            else:
                issues.append(
                    ConversionIssue(
                        "excluded-format",
                        file.path,
                        "Not a supported document format; excluded.",
                        False,
                    )
                )
            continue
        if format in {"md", "txt", "yaml"}:
            file_format = format
        try:
            text = file.data.decode("utf-8")
        except UnicodeError as error:
            fail("encoding", file.path, f"Expected UTF-8 text: {error}")
        documents.append(_parse(text, file_format, file.path))
    if not documents:
        fail("empty-input", "input", "No supported documents were selected.")
    validate_portable_context_name(placement)
    package_kind = "skill" if format == "skill" else "documents"
    root = Context.create(placement)
    contexts = [root]
    single = single_file and len(documents) == 1
    if not single:
        root.document = DocumentState("package", "md", "package", package_kind)
    by_name = {root.name: root}
    for document in documents:
        if single:
            context = root
        else:
            segments = [
                _segment(part) for part in PurePosixPath(document.state.path).parts
            ]
            if document.state.role == "skill_metadata":
                segments.append("metadata")
            for depth in range(1, len(segments)):
                parent_name = placement + "/" + "/".join(segments[:depth])
                if parent_name not in by_name:
                    parent = Context.create(parent_name)
                    parent.document = DocumentState(
                        "/".join(segments[:depth]), "md", "package", package_kind
                    )
                    contexts.append(parent)
                    by_name[parent_name] = parent
            name = placement + "/" + "/".join(segments)
            if name in by_name:
                fail(
                    "context-collision",
                    document.state.path,
                    f"Document placement collides at {name}.",
                )
            context = Context.create(name)
            contexts.append(context)
            by_name[name] = context
        context.document = replace(document.state, package=package_kind)
        for block in document.blocks:
            context.add(block.text)
    # Explicit Context membership makes the package navigable without inventing
    # additional original-file mapping records. Lexical recursion remains opt-in.
    for context in contexts[1:]:
        parent_name = context.name.rsplit("/", 1)[0]
        parent = by_name.get(parent_name, root)
        parent.add(context)
    attached_data = {}
    for file in attachments:
        digest = hashlib.sha256(file.data).hexdigest()
        root.attached_files.append(AttachedFile(file.path, digest))
        attached_data[digest] = file.data
    return MemContent(tuple(contexts), attached_data), tuple(issues)


def _document_from_context(context, state):
    texts = []
    for item in context.iter_items():
        if isinstance(item, Memory):
            texts.append(item.content)
        elif not isinstance(item, Context):
            fail(
                "unsupported-entry",
                context.name,
                "Document export requires directly owned Memories; materialize references explicitly first.",
            )
    if state.format == "yaml":
        text = ""
        for part in texts:
            if text and part and not text.endswith(("\n", "\r")):
                text += "\n"
            text += part
        return yaml.parse_yaml(text, state=state)
    blocks = []
    for text in texts:
        blocks.extend(_parse(text, state.format, state.path).blocks)
    return Document(state, tuple(blocks))


def convert_for_export(
    content,
    format=None,
    spacing_policy=SpacingPolicy(),
    *,
    skill_name=None,
    description=None,
):
    format = _ALIASES.get(format, format)
    if format == "mem":
        return mem.encode_mem(content), ()
    if format not in {None, "documents", "md", "txt", "yaml", "skill"}:
        fail("unsupported-format", "output", f"Unsupported format: {format}")
    contexts = content.contexts
    if not contexts:
        fail("empty-export", "output", "No Contexts were selected.")
    root = contexts[0]
    documents = []
    files = []
    issues = []
    selected_uids = {c.uid for c in contexts}
    for context in contexts:
        for item in context.iter_items():
            if isinstance(item, Context) and item.uid not in selected_uids:
                issues.append(
                    ConversionIssue(
                        "excluded-context",
                        item.name,
                        "Context is outside the selected scope; use -r to include lexical descendants.",
                        False,
                    )
                )
        state = context.document
        if state is not None and state.role == "package":
            if any(isinstance(item, Memory) for item in context.iter_items()):
                fail(
                    "unplaced-memory",
                    context.name,
                    "Package Context contains new text; move it into a document Context before exporting.",
                )
        else:
            if state is None:
                relative = (
                    context.name[len(root.name) + 1 :]
                    if context.name.startswith(root.name + "/")
                    else root.name.rsplit("/", 1)[-1]
                )
                selected_format = format if format in {"md", "txt", "yaml"} else "md"
                state = DocumentState(relative + "." + selected_format, selected_format)
                if format == "skill" and context is root:
                    state = DocumentState("SKILL.md", "md", "skill_body", "skill")
                elif format == "skill" and context.name == root.name + "/metadata":
                    state = DocumentState("SKILL.md", "yaml", "skill_metadata", "skill")
            elif format in {"md", "txt", "yaml"} and state.role == "document":
                state = replace(
                    state,
                    format=format,
                    path=str(PurePosixPath(state.path).with_suffix("." + format)),
                )
            documents.append(_document_from_context(context, state))
        for file in context.attached_files:
            data = content.attached_data.get(file.sha256)
            if data is None or hashlib.sha256(data).hexdigest() != file.sha256:
                fail(
                    "missing-attachment",
                    file.path,
                    "Attached-file bytes are missing or damaged.",
                )
            files.append(OutputFile(file.path, data, True))
    is_skill = format == "skill" or any(
        d.state.role.startswith("skill_") for d in documents
    )
    if is_skill:
        if format == "skill" and not any(
            d.state.role == "skill_body" for d in documents
        ):
            candidates = [d for d in documents if d.state.role == "document"]
            if len(candidates) != 1:
                fail(
                    "skill-body",
                    "SKILL.md",
                    "Select one body document when creating a new skill.",
                )
            body = candidates[0]
            documents = [
                replace(
                    d,
                    state=replace(
                        d.state,
                        path="SKILL.md",
                        format="md",
                        role="skill_body",
                        package="skill",
                    ),
                )
                if d is body
                else d
                for d in documents
            ]
        if skill_name is not None and any(
            d.state.role == "skill_metadata" for d in documents
        ):
            fail(
                "existing-metadata",
                "SKILL.md",
                "Edit the existing metadata Context instead of supplying replacement metadata options.",
            )
        if (
            not any(d.state.role == "skill_metadata" for d in documents)
            and skill_name is not None
            and description is not None
        ):
            import yaml as yaml_library

            header = yaml_library.safe_dump(
                {"name": skill_name, "description": description},
                sort_keys=False,
                allow_unicode=True,
            )
            documents.append(
                yaml.parse_yaml(
                    header,
                    state=DocumentState("SKILL.md", "yaml", "skill_metadata", "skill"),
                )
            )
        package = DocumentPackage(tuple(documents), format=PackageFormat.SKILL)
        files.append(
            OutputFile(
                "SKILL.md", skill.render_skill(package, spacing_policy).encode("utf-8")
            )
        )
    for document in documents:
        if document.state.role.startswith("skill_"):
            continue
        renderer = {
            "md": markdown.render_markdown,
            "txt": plain_text.render_text,
            "yaml": yaml.render_yaml,
        }[document.state.format]
        text = (
            renderer(document)
            if document.state.format == "yaml"
            else renderer(document, spacing_policy)
        )
        files.append(OutputFile(document.state.path, text.encode("utf-8")))
    if not files:
        fail(
            "empty-export",
            root.name,
            "No documents selected; use -r for a package Context.",
        )
    issues.extend(validate_output_files(tuple(files), "skill" if is_skill else format))
    return tuple(files), tuple(issues)


def validate_output_files(files, format=None):
    paths = []
    for file in files:
        relative_document_path(file.path)
        if file.path.casefold() in {p.casefold() for p in paths}:
            fail(
                "duplicate-output",
                file.path,
                "Two entries produce the same output path.",
            )
        if any(
            file.path.startswith(p + "/") or p.startswith(file.path + "/")
            for p in paths
        ):
            fail(
                "output-path-conflict",
                file.path,
                "An output file is also used as a directory.",
            )
        paths.append(file.path)
    issues = []
    parser = MarkdownIt("commonmark")
    for file in files:
        if file.attached or not file.path.lower().endswith(".md"):
            continue
        tokens = parser.parse(file.data.decode("utf-8"))
        for token in tokens:
            for child in token.children or ():
                link = (
                    child.attrGet("href")
                    if child.type == "link_open"
                    else child.attrGet("src")
                    if child.type == "image"
                    else None
                )
                if not link:
                    continue
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                target = posixpath.normpath(
                    posixpath.join(posixpath.dirname(file.path), unquote(parsed.path))
                )
                if target not in paths and not any(
                    p.startswith(target.rstrip("/") + "/") for p in paths
                ):
                    issues.append(
                        ConversionIssue(
                            "unresolved-link",
                            file.path,
                            f"Reference is not present in output: {link}",
                            False,
                        )
                    )
    return tuple(issues)
