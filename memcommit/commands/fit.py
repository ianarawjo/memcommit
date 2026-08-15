"""Run and inspect revision-bound Fit judgments for one Ground."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.command_progress import CommandProgress
from memcommit.fit import FitError, FitReport
from memcommit.fit_runtime import execute_and_save_ground_fit
from memcommit.fit_store import FitStore
from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore


def render_fit(report: FitReport, *, current: bool = True) -> str:
    identity = report.provider_identity
    example_by_uid = {example.uid: example for example in report.examples}
    rule_alias = {rule.uid: rule.alias for rule in report.rules}
    counts = {
        status: sum(judgment.status == status for judgment in report.judgments)
        for status in ("FIT", "CONTRADICTS", "UNDERDETERMINED", "NOT_APPLICABLE")
    }
    lines = [
        f"FIT · {safe_terminal_text(report.ground_name)} · REVISION {report.ground_revision}",
        "STATUS · READ-ONLY · " + ("CURRENT" if current else "STALE"),
        f"RULES {len(report.rules)} · EXAMPLES {len(report.examples)}",
        "PROVIDER · "
        + (identity.display_name() if identity is not None else "UNRECORDED"),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(report.overview),
        "",
        "EXAMPLE FIT",
    ]
    for judgment in report.judgments:
        example = example_by_uid[judgment.example_uid]
        lines.extend(
            [
                "",
                f"{example.alias} · {judgment.status} · RULES "
                + ", ".join(rule_alias[uid] for uid in judgment.rule_uids),
                f"  {safe_terminal_text(example.statement)}",
                f"  WHY · {safe_terminal_text(judgment.reason)}",
            ]
        )
        if judgment.observed:
            lines.append(f"  OBSERVED · {safe_terminal_text(judgment.observed)}")
    lines.extend(
        [
            "",
            "TOTALS · "
            + " · ".join(f"{status} {counts[status]}" for status in counts),
            f"RECEIPT · {report.uid} · {report.digest}",
            "GROUND DIGEST · " + report.ground_digest,
        ]
    )
    if not current:
        lines.append("STALE · Ground changed after this immutable Fit receipt.")
    return "\n".join(lines)


def cmd(
    ground_name: Annotated[
        str,
        typer.Argument(help="Saved Ground whose active Examples are fitted"),
    ],
    receipt: Annotated[
        Optional[str],
        typer.Option(
            "--receipt",
            help="Show one immutable Fit receipt by exact uid instead of running Fit",
        ),
    ] = None,
) -> None:
    """Fit every active Ground Example to the active Rules without changing Ground."""

    store = MemoryStore(create=False)
    try:
        fit_store = FitStore(store)
        if receipt is not None:
            report = fit_store.load(receipt)
            if report.ground_name != ground_name:
                raise FitError("The Fit receipt belongs to a different Ground.")
            session = store.load_ground_session(ground_name)
            if session is None:
                raise FitError(f"Ground '{ground_name}' was not found.")
            current = fit_store.latest_for_ground(session)
            is_current = (
                current is not None
                and current.report.uid == report.uid
                and current.current
            )
        else:
            with CommandProgress("FIT", "judging every Ground Example", total=1) as progress:
                report = execute_and_save_ground_fit(
                    store=store,
                    ground_name=ground_name,
                    provider_factory=connect_semantic_provider,
                )
                progress.update("receipt saved", step=1)
            is_current = True
        typer.echo(render_fit(report, current=is_current))
    except (
        FitError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Fit error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
