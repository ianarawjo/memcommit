"""Terminal formatting for the prepared current-Context listing."""

import shutil

import typer
from prompt_toolkit.utils import get_cwidth

from memcommit.core.uid_prefixes import extend_uid_prefixes_until_unique
from memcommit.models.memory import Memory


_MIN_MEMORY_CONTENT_WIDTH = 20


def _wrap_memory_content_to_width(content: str, width: int) -> tuple[str, ...]:
    """Wrap normalized text by terminal cells while preserving word boundaries."""

    words_in_content = content.split(" ")
    word_parts_in_content: list[str] = []

    for word in words_in_content:
        if get_cwidth(word) > width:
            word_parts_in_content.extend(
                _split_long_word_to_width(word, width)
            )
        else:
            word_parts_in_content.append(word)

    lines: list[str] = [""]

    for word_part in word_parts_in_content:
        current_line = lines[-1]
        if current_line == "":
            current_line = word_part
        else:
            current_line = f"{current_line} {word_part}"

        if get_cwidth(current_line) > width:
            lines.append(word_part)
            continue

        lines[-1] = current_line

    return tuple(lines)


def _split_long_word_to_width(
    long_word: str,
    width: int,
) -> list[str]:
    word_parts_within_width: list[str] = []
    current_word_part = ""

    for character in long_word:
        if (
            current_word_part
            and get_cwidth(current_word_part + character) > width
        ):
            word_parts_within_width.append(current_word_part)
            current_word_part = ""

        current_word_part += character

    if current_word_part:
        word_parts_within_width.append(current_word_part)

    return word_parts_within_width


def _format_memory_content_with_label(
    label: str,
    content: str,
    *,
    indent: int,
    terminal_width: int,
) -> tuple[str, ...]:
    """Put content beside its selector and align visual continuation rows."""

    label_width = get_cwidth(label)
    available_content_width = terminal_width - (label_width + 1)
    if available_content_width < _MIN_MEMORY_CONTENT_WIDTH:
        content_indent = " " * (indent + 2)
        fallback_width = max(
            _MIN_MEMORY_CONTENT_WIDTH,
            terminal_width - get_cwidth(content_indent),
        )
        wrapped_content_lines = _wrap_memory_content_to_width(content, fallback_width)
        return (label, *(content_indent + line for line in wrapped_content_lines))
    content_indent = " " * (label_width + 1)
    wrapped_content_lines = _wrap_memory_content_to_width(content, available_content_width)
    return (
        f"{label} {wrapped_content_lines[0]}",
        *(content_indent + line for line in wrapped_content_lines[1:]),
    )


def render_list_receipt(
    context_name: str,
    ordered_memory_list: tuple[Memory, ...],
    child_context_names: tuple[str, ...],
) -> None:
    uid_prefixes_by_uid = extend_uid_prefixes_until_unique(
        memory.uid for memory in ordered_memory_list
    )
    terminal_width = shutil.get_terminal_size(fallback=(100, 24)).columns

    typer.secho(f"Context: {context_name}", bold=True)
    memory_noun = "memory" if len(ordered_memory_list) == 1 else "memories"
    subcontext_noun = "subcontext" if len(child_context_names) == 1 else "subcontexts"
    typer.echo(f"  {len(ordered_memory_list)} {memory_noun}")
    typer.echo(f"  {len(child_context_names)} {subcontext_noun}")
    typer.echo()
    if not child_context_names and not ordered_memory_list:
        typer.echo("  (empty)")
        return

    for child_name in child_context_names:
        typer.echo(f"  DESCENDANT · [context] {child_name}")
    if child_context_names and ordered_memory_list:
        typer.echo()

    for memory in ordered_memory_list:
        memory_uid_prefix = uid_prefixes_by_uid[memory.uid]
        label = f"  [memory {memory_uid_prefix}]"
        display_content = " ".join(memory.content.split())
        if not display_content:
            display_content = "(empty)"
        for line in _format_memory_content_with_label(
            label,
            display_content,
            indent=2,
            terminal_width=terminal_width,
        ):
            typer.echo(line)
