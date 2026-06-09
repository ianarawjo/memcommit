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
