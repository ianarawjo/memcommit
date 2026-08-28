"""Cross-interface identity checks for command-review values."""

from importlib.util import find_spec

from memcommit.adapters.console.coordination.command_review import (
    CommandReview as PublicCommandReview,
)
from memcommit.adapters.console.coordination.command_review.model import CommandReview
from memcommit.adapters.console.terminal.components.exact_command_review import (
    CommandReview as TuiCommandReview,
    render_exact_command_review,
)


def test_tui_command_review_uses_the_shared_value_type():
    assert PublicCommandReview is CommandReview
    assert TuiCommandReview is CommandReview


def test_review_from_shared_owner_renders_through_tui_component():
    review = CommandReview(
        argv=("mem", "rename", "old", "new"),
        effects=("Rename Context 'old' to 'new'.",),
    )

    rendered = render_exact_command_review(review)

    assert "mem rename old new" in rendered
    assert "Rename Context 'old' to 'new'." in rendered


def test_review_owns_immutable_copies_of_caller_sequences():
    argv = ["mem", "init", "draft"]
    effects = ["Create Context 'draft'."]

    review = CommandReview(argv=argv, effects=effects)  # type: ignore[arg-type]
    argv.append("changed")
    effects.append("Changed after review.")

    assert review.argv == ("mem", "init", "draft")
    assert review.effects == ("Create Context 'draft'.",)


def test_pre_command_review_shared_module_is_unavailable():
    assert find_spec("memcommit.adapters.console.coordination.exact_command_review") is None
