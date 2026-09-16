"""Detailed Help requirements owned by Init Study."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


INIT_STUDY_SHELL_REQUIREMENT = (
    "mem init-study requires zsh to be installed and available on PATH "
    "to start an isolated Study shell using the "
    "run_isolated_study_shell() function."
)

INIT_STUDY_DETAILS = (
    OperationTextDetail(
        id="isolated-study-shell",
        operation="init-study",
        title="RUNNING AN ISOLATED STUDY SHELL",
        use_when=(
            "Checking the requirements and tested platform scope "
            "of an isolated Study shell."
        ),
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            f"{INIT_STUDY_SHELL_REQUIREMENT} "
            "The shell separates its command history from the existing shell "
            "so that commands from previous Study sessions or other "
            "participants do not appear during ordinary history navigation. "
            "This isolation was introduced after participants were observed "
            "recalling previous commands using arrow keys and shell history "
            "search during the pilot study. "
            "The run_isolated_study_shell() function has been tested only "
            "on macOS; its behavior on other platforms has not been verified."
        ),
    ),
)


__all__ = ["INIT_STUDY_SHELL_REQUIREMENT", "INIT_STUDY_DETAILS"]
