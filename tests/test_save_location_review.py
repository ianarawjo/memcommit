from __future__ import annotations

from memcommit.adapters.console.terminal.components.save_location_review import review_save_location


def test_save_location_card_can_edit_the_exact_name_before_apply(
    monkeypatch,
    capsys,
):
    replies = iter(("e", "task-3/final", "y"))
    validated: list[str] = []
    monkeypatch.setattr(
        "memcommit.adapters.console.terminal.components.save_location_review.typer.prompt",
        lambda *args, **kwargs: next(replies),
    )

    result = review_save_location(
        "task-3/draft",
        validate=validated.append,
        apply_label="create Result Context",
    )

    assert result == "task-3/final"
    assert validated == [
        "task-3/draft",
        "task-3/final",
        "task-3/final",
    ]
    rendered = capsys.readouterr().out
    assert "SAVE LOCATION" in rendered
    assert "task-3/draft" in rendered
    assert "task-3/final" in rendered
