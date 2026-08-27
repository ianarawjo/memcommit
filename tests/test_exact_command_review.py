"""Cross-interface identity checks for exact-command review values."""

from memcommit.commands.shared.exact_command_review import (
    ExactCommandReview as LegacyCommandReview,
)
from memcommit.exact_command_review import ExactCommandReview
from memcommit.adapters.interfaces.tui.components.exact_command_review import (
    ExactCommandReview as TuiCommandReview,
    render_exact_command_review,
)


def test_all_exact_command_review_paths_share_one_value_type():
    assert LegacyCommandReview is ExactCommandReview
    assert TuiCommandReview is ExactCommandReview


def test_review_from_neutral_owner_renders_through_tui_component():
    review = ExactCommandReview(
        argv=("mem", "rename", "old", "new"),
        effects=("Rename Context 'old' to 'new'.",),
    )

    rendered = render_exact_command_review(review)

    assert "mem rename old new" in rendered
    assert "Rename Context 'old' to 'new'." in rendered


def test_review_owns_immutable_copies_of_caller_sequences():
    argv = ["mem", "init", "draft"]
    effects = ["Create Context 'draft'."]

    review = ExactCommandReview(argv=argv, effects=effects)  # type: ignore[arg-type]
    argv.append("changed")
    effects.append("Changed after review.")

    assert review.argv == ("mem", "init", "draft")
    assert review.effects == ("Create Context 'draft'.",)
