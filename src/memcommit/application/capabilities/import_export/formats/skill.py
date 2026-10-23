"""Agent Skills composition; metadata is editable YAML, never opaque side data."""

from dataclasses import replace

import yaml

from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..model import DocumentPackage, PackageFormat, fail
from ..spacing import SpacingPolicy
from .markdown import parse_markdown, render_markdown
from .yaml import parse_yaml, render_yaml


def parse_skill(files, *, path_scope="PACKAGE") -> DocumentPackage:
    entries = [f for f in files if f.path == "SKILL.md"]
    if len(entries) != 1:
        fail("missing-skill", "SKILL.md", "A skill requires exactly one root SKILL.md.")
    try:
        text = entries[0].data.decode("utf-8")
    except UnicodeError as error:
        fail("encoding", "SKILL.md", str(error))
    opening, header, closing, content = split_skill_text(text)
    metadata = parse_yaml(
        header,
        state=CorrespondingDocumentMetadata(
            "SKILL.md", "yaml", "skill_metadata", "skill", opening, closing, path_scope
        ),
    )
    body = parse_markdown(
        content,
        state=CorrespondingDocumentMetadata(
            "SKILL.md", "md", "skill_body", "skill", path_scope=path_scope
        ),
    )
    package = DocumentPackage((body, metadata), format=PackageFormat.SKILL)
    validate_skill(package)
    return package


def split_skill_text(text):
    """Return raw delimiters, YAML and Markdown without changing whitespace."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").rstrip("\r\n") != "---":
        fail("frontmatter", "SKILL.md", "Expected YAML frontmatter delimited by ---.")
    end = next(
        (i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") in {"---", "..."}),
        None,
    )
    if end is None:
        fail("frontmatter", "SKILL.md", "YAML frontmatter has no closing delimiter.")
    return (
        lines[0],
        "".join(lines[1:end]),
        lines[end],
        "".join(lines[end + 1 :]),
    )


def validate_skill(package) -> dict:
    metadata = [d for d in package.documents if d.state.role == "skill_metadata"]
    if len(metadata) != 1:
        fail("skill-metadata", "SKILL.md", "Exactly one metadata Context is required.")
    try:
        text = render_yaml(metadata[0])
        node = yaml.compose(text, Loader=yaml.SafeLoader)
        if not isinstance(node, yaml.MappingNode):
            raise ValueError("Skill metadata must be a mapping.")
        keys = [key.value for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise ValueError("Skill metadata repeats a key.")
        values = yaml.safe_load(text)
        name = values.get("name")
        description = values.get("description")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 64
            or name.startswith("-")
            or name.endswith("-")
            or "--" in name
            or not all(
                c == "-" or c.isdigit() or (c.isalpha() and c.islower()) for c in name
            )
        ):
            raise ValueError(
                "name must be 1–64 lowercase letters/digits/hyphens without leading, trailing or repeated hyphens."
            )
        if (
            not isinstance(description, str)
            or not description.strip()
            or len(description) > 1024
        ):
            raise ValueError(
                "description must be nonempty text of at most 1024 characters."
            )
        for key in ("license", "allowed-tools", "compatibility"):
            if key in values and not isinstance(values[key], str):
                raise ValueError(f"{key} must be text.")
        if "compatibility" in values and not 1 <= len(values["compatibility"]) <= 500:
            raise ValueError("compatibility must be 1–500 characters.")
        if "metadata" in values and (
            not isinstance(values["metadata"], dict)
            or not all(
                isinstance(k, str) and isinstance(v, str)
                for k, v in values["metadata"].items()
            )
        ):
            raise ValueError("metadata must map string keys to string values.")
    except (yaml.YAMLError, ValueError, TypeError) as error:
        fail("skill-metadata", "SKILL.md", str(error))
    return values


def render_skill(package, policy=SpacingPolicy(), *, source_ranges=None) -> str:
    validate_skill(package)
    body = [d for d in package.documents if d.state.role == "skill_body"]
    if len(body) != 1:
        fail("skill-body", "SKILL.md", "Exactly one skill body is required.")
    metadata = next(d for d in package.documents if d.state.role == "skill_metadata")
    header_ranges, body_ranges = [], []
    header = render_yaml(metadata, source_ranges=header_ranges)
    if header and not header.endswith(("\n", "\r")):
        header += "\n"
    content = render_markdown(body[0], policy, source_ranges=body_ranges)
    opening = metadata.state.opening or "---\n"
    prefix = (
        opening
        + header
        + (metadata.state.closing or "---\n")
        + ("\n" if content and body[0].state.path_scope != "PROFILE" else "")
    )
    if source_ranges is not None:
        for spans, offset in (
            (header_ranges, len(opening.encode("utf-8"))),
            (body_ranges, len(prefix.encode("utf-8"))),
        ):
            source_ranges.extend(
                replace(span, start=span.start + offset, end=span.end + offset)
                for span in spans
            )
    return prefix + content
