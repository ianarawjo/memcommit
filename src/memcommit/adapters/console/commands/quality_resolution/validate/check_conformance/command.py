"""Run one read-only Rule Conformance check."""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.application.operations.quality_resolution.validate.check_conformance.model import (
    ConformanceError,
    ConformanceReport,
)
from memcommit.application.operations.quality_resolution.validate.check_conformance.runtime import (
    execute_context_conformance_with_rules_operand,
    execute_ground_conformance,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profiles.profile.config import ProfileConfigError
from memcommit.application.operations.profiles.profile.model import ProfileError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_semantic_provider,
)
from memcommit.persistence.store import MemoryStore


def render_conformance(report: ConformanceReport) -> str:
    """Render one compact receipt plus issue-only Context relationship rows."""

    examples = report.context_example_judgments
    applicable_examples = tuple(
        item for item in examples if item.status != "NOT_APPLICABLE"
    )
    applicable_rules = tuple(
        item for item in report.context_judgments if item.status != "NOT_APPLICABLE"
    )
    example_n_a = len(examples) - len(applicable_examples)
    rule_n_a = len(report.context_judgments) - len(applicable_rules)
    summary = (
        "CONFORMANCE · "
        f"{sum(item.status == 'CONFORMS' for item in applicable_examples)}/"
        f"{len(applicable_examples)} EXAMPLES CONFORM · "
        f"{sum(item.status == 'CONFORMS' for item in applicable_rules)}/"
        f"{len(applicable_rules)} RULES MET · "
        f"[EXAMPLES {display_escape_text(report.source_label)}] · "
        f"[RULES {display_escape_text(report.rules_label)}]"
    )
    if example_n_a:
        summary += (
            f" · {example_n_a} {'EXAMPLE' if example_n_a == 1 else 'EXAMPLES'} N/A"
        )
    if rule_n_a:
        summary += f" · {rule_n_a} {'RULE' if rule_n_a == 1 else 'RULES'} N/A"

    lines = [summary]
    rule_by_uid = {rule.uid: rule for rule in report.rules}
    subject_by_uid = {subject.uid: subject for subject in report.subjects}
    for judgment in report.context_judgments:
        rule = rule_by_uid[judgment.rule_uid]
        for case in judgment.nonconforming_cases:
            subject = subject_by_uid[case.subject_uid]
            lines.append(
                "! VIOLATES · "
                f"[EXAMPLE {display_escape_text(subject.alias)}] "
                f"{display_escape_text(subject.content)} · "
                f"[RULE {display_escape_text(rule.alias)}] "
                f"{display_escape_text(rule.content)} · WHY · "
                f"{display_escape_text(case.reason)}"
            )
        if judgment.status == "INSUFFICIENT_EVIDENCE":
            uncertain_subjects = tuple(
                subject_by_uid[uid] for uid in judgment.evidence_subject_uids
            )
            if uncertain_subjects:
                for subject in uncertain_subjects:
                    lines.append(
                        "? INSUFFICIENT_EVIDENCE · "
                        f"[EXAMPLE {display_escape_text(subject.alias)}] "
                        f"{display_escape_text(subject.content)} · "
                        f"[RULE {display_escape_text(rule.alias)}] "
                        f"{display_escape_text(rule.content)} · WHY · "
                        f"{display_escape_text(judgment.reason)}"
                    )
            else:
                lines.append(
                    "? INSUFFICIENT_EVIDENCE · "
                    f"[RULE {display_escape_text(rule.alias)}] "
                    f"{display_escape_text(rule.content)} · WHY · "
                    f"{display_escape_text(judgment.reason)}"
                )
    return "\n".join(lines)


def cmd(
    target_context: Annotated[
        Optional[str],
        typer.Argument(
            help="Existing local Context whose contents are checked against Rules"
        ),
    ] = None,
    rules_context: Annotated[
        Optional[list[str]],
        typer.Option(
            "--against",
            "--rule",
            "--from",
            metavar="RULES_SOURCE",
            help=(
                "Rules Context, unique local Memory UID/prefix, or literal "
                "Rule; use text:VALUE to force text; --against, --rule, and "
                "--from are equivalent"
            ),
        ),
    ] = None,
    subject_context: Annotated[
        Optional[list[str]],
        typer.Option(
            "--example",
            "--case",
            "--to",
            metavar="SUBJECT_CONTEXT",
            help=(
                "Example, Case, or other Target Context; --example, --case, "
                "and --to are equivalent"
            ),
        ),
    ] = None,
    ground: Annotated[
        Optional[str],
        typer.Option(
            "--ground",
            help="Saved Ground whose Example propositions are checked against its Rules",
        ),
    ] = None,
) -> None:
    """Check Ground Examples or one Context against Rules without changing either."""

    store = MemoryStore(create=False)
    try:
        rules_operands = tuple(rules_context or ())
        subject_operands = tuple(subject_context or ())
        if len(rules_operands) > 1:
            raise ConformanceError(
                "Use only one of --against, --rule, or --from; they are "
                "aliases for the Rules source."
            )
        if len(subject_operands) > 1:
            raise ConformanceError(
                "Use only one of --example, --case, or --to; they are "
                "aliases for the Subject Context."
            )
        if target_context is not None and subject_operands:
            raise ConformanceError(
                "Use the Target positional operand or --example/--case/--to, not both."
            )

        rules_locator = rules_operands[0] if rules_operands else None
        option_subject_locator = subject_operands[0] if subject_operands else None
        if ground is not None:
            if (
                target_context is not None
                or rules_locator is not None
                or option_subject_locator is not None
            ):
                raise ConformanceError(
                    "--ground cannot be combined with direct operands."
                )
            label = "checking Ground Examples"

            def run() -> ConformanceReport:
                return execute_ground_conformance(
                    store=store,
                    ground_name=ground,
                    provider_factory=connect_semantic_provider,
                )
        else:
            if rules_locator is None and option_subject_locator is None:
                raise ConformanceError(
                    "Context Conformance requires a Rules or Subject endpoint; "
                    "use --rule/--from, --example/--case/--to, or --ground."
                )
            snapshot = ContextOperandSnapshot.capture(store)
            subject_locator = option_subject_locator or target_context
            target_name = snapshot.resolve_or_current(subject_locator)
            if target_name is None:
                raise ConformanceError(
                    "Context Conformance needs an Example, Case, Target, or "
                    "current Context."
                )
            rules_operand = (
                rules_locator if rules_locator is not None else snapshot.current_name
            )
            if rules_operand is None:
                raise ConformanceError(
                    "Context Conformance needs a Rules source or a current Context."
                )
            label = "checking Context against Rules"

            def run() -> ConformanceReport:
                return execute_context_conformance_with_rules_operand(
                    store=store,
                    target_name=target_name,
                    rules_operand=rules_operand,
                    current_name=snapshot.current_name,
                    provider_factory=connect_semantic_provider,
                )

        with CommandProgress("CHECK CONFORMANCE", label, total=1) as progress:
            report = run()
            progress.update("report ready", step=1)
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
