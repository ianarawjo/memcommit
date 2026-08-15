"""Run one read-only Rule Conformance check."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.conformance import ConformanceError, ConformanceReport
from memcommit.conformance_runtime import (
    execute_context_conformance,
    execute_ground_conformance,
)
from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import QueryProviderError, connect_semantic_provider
from memcommit.store import MemoryStore


def render_conformance(report: ConformanceReport) -> str:
    """Render every typed judgment without implying mutation or enforcement."""

    identity = report.provider_identity
    lines = [
        f"CHECK CONFORMANCE · {report.mode}",
        "STATUS · READ-ONLY · COMPLETE · NO CONTEXT CHANGES",
        f"SUBJECT · {safe_terminal_text(report.source_label)}",
        f"RULES · {safe_terminal_text(report.rules_label)} · {len(report.rules)}",
        "PROVIDER · " + (identity.display_name() if identity is not None else "UNRECORDED"),
        "",
        "WHAT MEM UNDERSTOOD",
        safe_terminal_text(report.overview),
        "",
    ]
    rule_alias = {rule.uid: rule.alias for rule in report.rules}
    subject_by_uid = {subject.uid: subject for subject in report.subjects}
    if report.mode == "CASE":
        lines.append(f"CASE CONFORMANCE · {len(report.case_judgments)}")
        for judgment in report.case_judgments:
            subject = subject_by_uid[judgment.subject_uid]
            lines.extend(
                [
                    "",
                    f"{subject.alias} · {judgment.status} · RULES "
                    + ", ".join(rule_alias[uid] for uid in judgment.rule_uids),
                    f"  INPUT · {safe_terminal_text(subject.content)}",
                    f"  PREDICTED · {safe_terminal_text(judgment.predicted or '(none)')}",
                    f"  EXPECTED · {safe_terminal_text(subject.expected or '(none)')}",
                    f"  WHY · {safe_terminal_text(judgment.reason)}",
                ]
            )
    else:
        rule_by_uid = {rule.uid: rule for rule in report.rules}
        lines.append(f"CONTEXT CONFORMANCE · {len(report.context_judgments)} RULES")
        for judgment in report.context_judgments:
            rule = rule_by_uid[judgment.rule_uid]
            evidence = ", ".join(
                subject_by_uid[uid].alias for uid in judgment.evidence_subject_uids
            ) or "none"
            lines.extend(
                [
                    "",
                    f"{rule.alias} · {judgment.status}",
                    f"  RULE · {safe_terminal_text(rule.content)}",
                    f"  EVIDENCE · {evidence}",
                    f"  WHY · {safe_terminal_text(judgment.reason)}",
                ]
            )
        lines.extend(
            [
                "",
                f"OUTSIDE RULE JUDGMENTS · {len(report.outside_subject_uids)} Memories",
            ]
        )
    lines.extend(["", f"ISSUES · {report.issue_count}", f"REPORT DIGEST · {report.digest}"])
    return "\n".join(lines)


def cmd(
    target_context: Annotated[
        Optional[str],
        typer.Argument(
            help="Existing local Context whose contents are checked against Rules"
        ),
    ] = None,
    against: Annotated[
        Optional[str],
        typer.Option(
            "--against",
            help="Existing local Context whose direct Memories are Rules",
        ),
    ] = None,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Saved Ground whose Rules are replayed over expected Ground Memories",
        ),
    ] = None,
) -> None:
    """Check Ground cases or one Context against Rules without changing either."""

    store = MemoryStore(create=False)
    try:
        if ground is not None:
            if target_context is not None or against is not None:
                raise ConformanceError(
                    "--ground cannot be combined with a Target or --against."
                )
            label = "replaying Ground cases"

            def run() -> ConformanceReport:
                return execute_ground_conformance(
                    store=store,
                    ground_name=ground,
                    provider_factory=connect_semantic_provider,
                )
        else:
            if against is None:
                raise ConformanceError(
                    "Context Conformance requires --against RULE_CONTEXT."
                )
            snapshot = ContextOperandSnapshot.capture(store)
            target_name = snapshot.resolve_or_current(target_context)
            if target_name is None:
                raise ConformanceError(
                    "Context Conformance needs a Target or a current Context."
                )
            rules_name = snapshot.resolve(against)
            label = "checking Context against Rules"

            def run() -> ConformanceReport:
                return execute_context_conformance(
                    store=store,
                    target_name=target_name,
                    rules_name=rules_name,
                    provider_factory=connect_semantic_provider,
                )
        with CommandProgress("CHECK CONFORMANCE", label, total=1) as progress:
            report = run()
            progress.update("complete", step=1)
        typer.echo(render_conformance(report))
    except (
        ConformanceError,
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        ValueError,
    ) as error:
        typer.secho(
            "Conformance error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
