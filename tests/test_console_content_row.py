from __future__ import annotations

import pytest

from memcommit.adapters.console.content_row import render_numbered_content_row


def test_numbered_content_row_folds_but_never_shortens_content() -> None:
    content = "Rule prefix\n" + "complete-rule-content " * 80 + "Rule suffix."

    rendered = render_numbered_content_row(
        2,
        content,
        suffix="SUPPORT 11 · BOUNDARY 3",
    )

    assert rendered == (
        "[2] " + " ".join(content.split()) + " — SUPPORT 11 · BOUNDARY 3"
    )
    assert "Rule suffix." in rendered
    assert "…" not in rendered


@pytest.mark.parametrize(
    ("number", "content", "suffix"),
    ((0, "Rule.", "STATE"), (1, "", "STATE"), (1, "Rule.", "")),
)
def test_numbered_content_row_rejects_incomplete_rows(
    number: int,
    content: str,
    suffix: str,
) -> None:
    with pytest.raises(ValueError):
        render_numbered_content_row(number, content, suffix=suffix)
