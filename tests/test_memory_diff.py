"""Mechanical line and word contracts shared by mem diff and Impact."""

from memcommit.application.capabilities.reviewing.memory_diff import MemoryChange, memory_diff_lines


def _change(*, before: str | None, after: str | None) -> MemoryChange:
    return MemoryChange(
        marker="~",
        treatment="TEST",
        location="source → result",
        memory_uid="memory-1",
        before=before,
        after=after,
    )


def _text(line) -> str:
    return "".join(span.text for span in line.spans)


def test_identical_values_render_one_mechanical_equality_line() -> None:
    lines = memory_diff_lines(_change(before="Same Memory.", after="Same Memory."))

    assert [(line.marker, _text(line)) for line in lines] == [
        ("=", "Same Memory."),
    ]
    assert all(not span.changed for span in lines[0].spans)


def test_partial_change_marks_only_unequal_word_spans() -> None:
    lines = memory_diff_lines(
        _change(
            before="Use the north entrance until 10 p.m.",
            after="Use the south entrance until 8 p.m.",
        )
    )

    assert [(line.marker, _text(line)) for line in lines] == [
        ("-", "Use the north entrance until 10 p.m."),
        ("+", "Use the south entrance until 8 p.m."),
    ]
    assert [span.text for span in lines[0].spans if span.changed] == [
        "north",
        "10",
    ]
    assert [span.text for span in lines[1].spans if span.changed] == [
        "south",
        "8",
    ]


def test_multiline_diff_retains_equal_context_and_one_sided_lines() -> None:
    lines = memory_diff_lines(
        _change(
            before="Shared line.\nOld line.\nRemoved line.",
            after="Shared line.\nNew line.",
        )
    )

    assert [(line.marker, _text(line)) for line in lines] == [
        (" ", "Shared line."),
        ("-", "Old line."),
        ("+", "New line."),
        ("-", "Removed line."),
    ]


def test_add_and_remove_are_derived_only_from_missing_sides() -> None:
    addition = memory_diff_lines(_change(before=None, after="Added."))
    removal = memory_diff_lines(_change(before="Removed.", after=None))

    assert [(line.marker, _text(line)) for line in addition] == [("+", "Added.")]
    assert [(line.marker, _text(line)) for line in removal] == [("-", "Removed.")]
