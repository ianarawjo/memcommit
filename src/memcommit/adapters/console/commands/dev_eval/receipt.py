"""Render the scenario's completed boolean checks."""

from memcommit.adapters.console.terminal.core.output import echo_text
from memcommit.adapters.console.terminal.core.text import display_escape_text


def render_eval_receipt(
    checks: list[tuple[str, bool]], *, current_context_name: str | None
) -> None:
    """Present a completed evaluation without loading state or choosing an exit code."""

    # Keep the scenario's boolean-check contract; split its optional explanation
    # only for presentation, without deriving a verdict from the label.
    rows = [(name.partition(" · "), passed) for name, passed in checks]
    width = max(
        (len(display_escape_text(label)) for (label, separator, _), _ in rows if separator),
        default=0,
    )
    for (label, separator, description), passed in rows:
        status = "PASS" if passed else "FAIL"
        if separator:
            echo_text(
                "  {status}  {label:<{width}}  {description}",
                status=status,
                label=label,
                width=width,
                description=description,
            )
        else:
            echo_text("  {status}  {label}", status=status, label=label)
    echo_text("\nCurrent Context\n  {name}", name=current_context_name or "")
