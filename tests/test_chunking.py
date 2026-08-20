"""Unit tests for memcommit.chunking — pure text-splitting functions."""
import pytest

from memcommit.chunking import chunk_content, ChunkMethod, CHUNKING_METHODS


# ---------------------------------------------------------------------------
# paragraphs
# ---------------------------------------------------------------------------

def test_paragraphs_two_blocks():
    result = chunk_content("Block one.\n\nBlock two.", "paragraphs")
    assert result == ["Block one.", "Block two."]


def test_paragraphs_strips_whitespace():
    result = chunk_content("  Alpha  \n\n  Beta  ", "paragraphs")
    assert result == ["Alpha", "Beta"]


def test_paragraphs_multiple_blank_lines_count_as_one_split():
    result = chunk_content("A\n\n\n\nB", "paragraphs")
    assert result == ["A", "B"]


def test_paragraphs_single_block_returns_one_chunk():
    result = chunk_content("Just one paragraph.", "paragraphs")
    assert result == ["Just one paragraph."]


def test_paragraphs_empty_string_returns_empty():
    assert chunk_content("", "paragraphs") == []


def test_paragraphs_enum_value_accepted():
    result = chunk_content("X\n\nY", ChunkMethod.paragraphs)
    assert result == ["X", "Y"]


# ---------------------------------------------------------------------------
# sentences
# ---------------------------------------------------------------------------

def test_sentences_basic_split():
    result = chunk_content("Hello world. This is a test. Another sentence.", "sentences")
    assert result[0] == "Hello world."
    assert "This is a test." in result


def test_sentences_splits_on_exclamation_and_question():
    result = chunk_content("Wow! Really? Yes.", "sentences")
    assert len(result) == 3


def test_sentences_single_sentence():
    result = chunk_content("Only one sentence.", "sentences")
    assert result == ["Only one sentence."]


def test_sentences_does_not_require_latin_uppercase_after_boundary():
    result = chunk_content("첫 문장입니다. 다음 문장입니다. 마지막입니다.", "sentences")
    assert result == ["첫 문장입니다.", "다음 문장입니다.", "마지막입니다."]


def test_sentences_keeps_closing_quote_with_preceding_sentence():
    result = chunk_content('She said "Done." then she left.', "sentences")
    assert result == ['She said "Done."', "then she left."]


# ---------------------------------------------------------------------------
# clauses and literal boundaries
# ---------------------------------------------------------------------------

def test_clauses_splits_strong_punctuation_but_not_commas():
    result = chunk_content(
        "Alpha, beta; Gamma: Delta — Epsilon. Zeta?",
        "clauses",
    )
    assert result == [
        "Alpha, beta;",
        "Gamma:",
        "Delta —",
        "Epsilon.",
        "Zeta?",
    ]


def test_clauses_requires_whitespace_after_internal_punctuation():
    result = chunk_content("Version 1.2 and https://example.com stay. Next.", "clauses")
    assert result == ["Version 1.2 and https://example.com stay.", "Next."]


def test_clauses_keeps_repeated_punctuation_and_quote_together():
    result = chunk_content('Really?!" Next; then.', "clauses")
    assert result == ['Really?!"', "Next;", "then."]


def test_break_on_adds_literal_comma_boundaries_without_regex_meaning():
    result = chunk_content("Alpha,beta]gamma. Delta.", "sentences", break_on=",]")
    assert result == ["Alpha,", "beta]", "gamma.", "Delta."]


@pytest.mark.parametrize("break_on", ["", "a", "1", ", "])
def test_break_on_rejects_empty_or_non_punctuation_boundaries(break_on):
    with pytest.raises(ValueError, match="break_on"):
        chunk_content("Alpha, beta.", "sentences", break_on=break_on)


# ---------------------------------------------------------------------------
# character limits
# ---------------------------------------------------------------------------

def test_max_chars_packs_complete_sentences_up_to_hard_limit():
    result = chunk_content(
        "One short sentence. Another short sentence. Tail.",
        "sentences",
        max_chars=30,
    )
    assert result == ["One short sentence.", "Another short sentence. Tail."]
    assert all(len(chunk) <= 30 for chunk in result)


def test_max_chars_splits_oversized_unit_at_whitespace():
    result = chunk_content("alpha beta gamma", "sentences", max_chars=10)
    assert result == ["alpha beta", "gamma"]


def test_max_chars_splits_one_oversized_token_without_losing_characters():
    result = chunk_content("abcdefghij", "sentences", max_chars=4)
    assert result == ["abcd", "efgh", "ij"]
    assert "".join(result) == "abcdefghij"


def test_min_chars_groups_adjacent_units_and_absorbs_final_remainder():
    result = chunk_content("One. Two. Three.", "sentences", min_chars=8)
    assert result == ["One. Two. Three."]


def test_min_and_max_chars_keep_an_unavoidable_short_edge_chunk():
    result = chunk_content(
        "abcdefghij",
        "sentences",
        min_chars=4,
        max_chars=4,
    )
    assert result == ["abcd", "efgh", "ij"]


def test_length_packing_preserves_internal_paragraph_separator():
    result = chunk_content("Alpha.\n\nBeta.", "paragraphs", max_chars=20)
    assert result == ["Alpha.\n\nBeta."]


def test_break_on_and_limits_compose_in_source_order():
    result = chunk_content(
        "Alpha, beta, gamma.",
        "sentences",
        break_on=",",
        min_chars=8,
        max_chars=12,
    )
    assert result == ["Alpha, beta,", "gamma."]


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"min_chars": 0}, "min_chars"),
        ({"max_chars": -1}, "max_chars"),
        ({"min_chars": True}, "min_chars"),
        ({"min_chars": 8, "max_chars": 4}, "greater"),
    ],
)
def test_invalid_character_limits_raise_value_error(options, message):
    with pytest.raises(ValueError, match=message):
        chunk_content("Alpha. Beta.", "sentences", **options)


# ---------------------------------------------------------------------------
# markdown_headers
# ---------------------------------------------------------------------------

MARKDOWN_DOC = """\
# Section One
Content of section one.

# Section Two
Content of section two.
"""

def test_markdown_headers_splits_on_h1():
    result = chunk_content(MARKDOWN_DOC, "markdown_headers")
    assert len(result) == 2
    assert result[0].startswith("# Section One")
    assert result[1].startswith("# Section Two")


def test_markdown_headers_no_repeating_header_returns_original():
    content = "# Unique header\nSome text."
    result = chunk_content(content, "markdown_headers")
    assert len(result) == 1


def test_markdown_headers_empty_returns_empty():
    assert chunk_content("", "markdown_headers") == []


def test_markdown_headers_preserves_subheadings_inside_chunk():
    content = "# A\n## Sub\ntext\n# B\nmore"
    result = chunk_content(content, "markdown_headers")
    assert len(result) == 2
    assert "## Sub" in result[0]


# ---------------------------------------------------------------------------
# unknown method
# ---------------------------------------------------------------------------

def test_unknown_method_raises_value_error():
    with pytest.raises(ValueError, match="Unknown chunking method"):
        chunk_content("text", "not_a_method")


# ---------------------------------------------------------------------------
# CHUNKING_METHODS registry
# ---------------------------------------------------------------------------

def test_chunking_methods_contains_all_enum_values():
    for method in ChunkMethod:
        assert method.value in CHUNKING_METHODS
