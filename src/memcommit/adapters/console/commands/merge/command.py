"""Public Merge entrypoint over unchanged semantic and literal workflows."""

from typing import Annotated, Optional
import typer
from memcommit.adapters.console.coordination.context_scope_options import (
    legacy_root_only_option_alias,
)

SEMANTIC_PARAMETERS = (
    "left",
    "right",
    "result",
    "into",
    "to",
    "from_",
    "issue",
    "choice",
    "comment",
    "expect_session",
    "preserve_all",
    "defer_all",
    "accept",
    "restart",
    "revision",
    "revises_turn",
    "expand",
    "sessions",
    "direct",
    "recursive",
    "left_descendants",
    "right_descendants",
    "memory",
    "incoming_memory",
    "baseline_memory",
)
SEMANTIC_ONLY = (
    "result",
    "issue",
    "choice",
    "comment",
    "expect_session",
    "preserve_all",
    "defer_all",
    "accept",
    "restart",
    "revision",
    "revises_turn",
    "expand",
    "sessions",
    "left_descendants",
    "right_descendants",
    "memory",
    "incoming_memory",
    "baseline_memory",
)


def cmd(
    left: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional INCOMING A, or symmetric PEER A when a third "
                "RESULT or two-source --to is supplied; an unambiguously "
                "non-Context sole sentence is inline Memory content"
            )
        ),
    ] = None,
    right: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Directional BASELINE B, or symmetric PEER B when a third "
                "RESULT or two-source --to is supplied"
            )
        ),
    ] = None,
    result: Annotated[
        Optional[str],
        typer.Argument(
            help=("Symmetric RESULT C; equivalent to --to and created when absent")
        ),
    ] = None,
    into: Annotated[
        Optional[str],
        typer.Option(
            "--into",
            help=(
                "Explicit directional BASELINE alias for 'mem merge INCOMING BASELINE'"
            ),
        ),
    ] = None,
    to: Annotated[
        Optional[str],
        typer.Option(
            "--to",
            help=(
                "Directional BASELINE when fewer than two positional sources "
                "are supplied; otherwise symmetric RESULT C, created when absent"
            ),
        ),
    ] = None,
    from_: Annotated[
        Optional[str],
        typer.Option(
            "--from",
            help=(
                "Directional INCOMING Context or unambiguous inline Memory; "
                "--to may name BASELINE, otherwise current supplies it"
            ),
        ),
    ] = None,
    issue: Annotated[
        Optional[str],
        typer.Option(
            "--issue",
            help="Issue number or unique uid prefix for this comment",
        ),
    ] = None,
    choice: Annotated[
        Optional[int],
        typer.Option(
            "--choice",
            min=1,
            help="Choose one displayed reading for --issue",
        ),
    ] = None,
    comment: Annotated[
        Optional[str],
        typer.Option(
            "--comment",
            help="Explain one issue or guide all remaining relations",
        ),
    ] = None,
    expect_session: Annotated[
        Optional[str],
        typer.Option(
            "--expect-session",
            metavar="SHA256",
            help="Require the exact saved Merge revision reviewed for this turn",
        ),
    ] = None,
    preserve_all: Annotated[
        bool,
        typer.Option(
            "--preserve-all",
            help="Ask to retain every remaining source distinction",
        ),
    ] = False,
    defer_all: Annotated[
        bool,
        typer.Option(
            "--defer-all",
            help="Close as review-only without applying the target",
        ),
    ] = False,
    accept: Annotated[
        bool,
        typer.Option(
            "--accept",
            help="Apply the exact ready proposal without another model call",
        ),
    ] = False,
    restart: Annotated[
        bool,
        typer.Option(
            "--restart",
            help=(
                "Replace the saved review session after rechecking its bound Contexts"
            ),
        ),
    ] = False,
    revision: Annotated[
        Optional[str],
        typer.Option(
            "--revision",
            help="How the comment relates to prior dialogue",
        ),
    ] = None,
    revises_turn: Annotated[
        list[str] | None,
        typer.Option(
            "--revises-turn",
            help="Prior turn uid for a correction or retraction",
        ),
    ] = None,
    expand: Annotated[
        Optional[str],
        typer.Option(
            "--expand",
            help="Render one issue's complete options provider-free",
        ),
    ] = None,
    sessions: Annotated[
        bool,
        typer.Option(
            "--sessions",
            help="Enter the interactive Merge session launcher",
        ),
    ] = False,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Use only the selected LEFT/INCOMING and RIGHT/BASELINE roots",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help="Include descendants under both Merge roots",
        ),
    ] = False,
    left_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--left-descendants/--left-root-only",
            legacy_root_only_option_alias("left"),
            help="Include all readable descendants under PEER or INCOMING A",
        ),
    ] = None,
    right_descendants: Annotated[
        Optional[bool],
        typer.Option(
            "--right-descendants/--right-root-only",
            legacy_root_only_option_alias("right"),
            help=(
                "Include readable descendants under PEER B, or writable "
                "owner Contexts under directional BASELINE B"
            ),
        ),
    ] = None,
    memory: Annotated[
        Optional[str],
        typer.Option(
            "--memory",
            "-m",
            help=(
                "Use exact text as one process-local INCOMING Memory; the "
                "current Context, --into, or directional --to supplies BASELINE"
            ),
        ),
    ] = None,
    incoming_memory: Annotated[
        Optional[str],
        typer.Option(
            "--incoming-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Merge, select one INCOMING Memory while its "
                "neighbors remain non-actionable context"
            ),
        ),
    ] = None,
    baseline_memory: Annotated[
        Optional[str],
        typer.Option(
            "--baseline-memory",
            metavar="UID_OR_PREFIX",
            help=(
                "In directional Merge, restrict mutation to one BASELINE Memory "
                "while its neighbors remain non-actionable context"
            ),
        ),
    ] = None,
    literal: Annotated[
        bool,
        typer.Option(
            "--literal",
            help="Use stored-item merging without semantic inference; retain the existing literal conflict and recursive behavior.",
        ),
    ] = False,
    resolution: Annotated[
        Optional[list[str]],
        typer.Option(
            "--resolve",
            help="With --literal: ID=keep-target or ID=take-source; repeat for every conflict.",
        ),
    ] = None,
    keep_target_all: Annotated[
        bool,
        typer.Option(
            "--keep-target-all", help="With --literal: keep Target for every conflict."
        ),
    ] = False,
    take_source_all: Annotated[
        bool,
        typer.Option(
            "--take-source-all", help="With --literal: take Source for every conflict."
        ),
    ] = False,
) -> None:
    """Merge semantically by default; --literal selects stored-item merging."""
    values = locals().copy()
    semantic_flags = {"preserve_all", "defer_all", "accept", "restart", "sessions"}
    if literal:
        # Dispatch before either implementation opens a Store or provider. Keeping
        # each parser authoritative preserves the two established operand grammars.
        incompatible = [
            name
            for name in SEMANTIC_ONLY
            if (
                values[name]
                if name in semantic_flags
                else values[name] is not None and values[name] != []
            )
        ]
        if incompatible:
            options = ", ".join(
                "RESULT" if name == "result" else "--" + name.replace("_", "-")
                for name in incompatible
            )
            raise typer.BadParameter(
                f"{options} require semantic Merge; remove --literal."
            )
        from memcommit.adapters.console.commands.merge.literal.command import (
            cmd as run_literal,
        )

        run_literal(
            source=left,
            target=right,
            from_=from_,
            into=into,
            to=to,
            direct=direct,
            recursive=recursive,
            resolution=resolution,
            keep_target_all=keep_target_all,
            take_source_all=take_source_all,
        )
        return
    if resolution is not None or keep_target_all or take_source_all:
        raise typer.BadParameter(
            "--resolve, --keep-target-all, and --take-source-all require --literal."
        )
    from memcommit.adapters.console.commands.merge.semantic.entrypoint import (
        cmd as run_semantic,
    )

    run_semantic(**{name: values[name] for name in SEMANTIC_PARAMETERS})
