"""Immediate document Export CLI; no workbench or review session."""

from pathlib import Path
from typing import Annotated, Optional
import typer

from memcommit.application.operations.mem_export.application import (
    ExportRequest,
    run_export,
)
from memcommit.application.operations.mem_export.runtime import ExportRuntime
from .receipt import render_export_receipt, render_export_error


def cmd(
    source: Annotated[
        Optional[str],
        typer.Argument(help="Source Context; defaults to the current Context."),
    ] = None,
    destination: Annotated[
        Optional[Path],
        typer.Option(
            "--to",
            help="New output directory; existing destinations are never overwritten.",
        ),
    ] = None,
    format: Annotated[
        Optional[str],
        typer.Option(
            "--format",
            help="md, txt, yaml, skill, or mem; defaults to the stored document format.",
        ),
    ] = None,
    recursive: Annotated[
        bool,
        typer.Option("--recursive", "-r", help="Include lexical descendant Contexts."),
    ] = False,
    skill_name: Annotated[
        Optional[str],
        typer.Option(
            "--skill-name",
            help="Name for a new skill without an existing metadata Context.",
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option("--description", help="Description for a new skill."),
    ] = None,
):
    try:
        result = run_export(
            ExportRequest(
                source, destination, format, recursive, skill_name, description
            ),
            ExportRuntime(),
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        render_export_error(error)
        raise typer.Exit(1) from error
    render_export_receipt(result)
