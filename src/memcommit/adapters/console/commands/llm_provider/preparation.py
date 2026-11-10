"""Codex installation/login recovery and first-use checked configuration."""

import sys

from memcommit.adapters.console.commands.llm_provider.installation import (
    find_provider_binary,
    install_provider_runtime,
    login_provider,
    provider_install_description,
)
from memcommit.adapters.console.commands.llm_provider.screen import (
    run_provider_configuration_screen,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.components.selection.screen import (
    run_selection_screen,
)
from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.llm_provider.codex_configuration import (
    connect_checked_codex_provider,
    load_codex_configuration_catalog,
    select_codex_configuration,
)
from memcommit.llm_providers.errors import QueryProviderError


class ProviderPreparationCancelled(Exception):
    """The person left provider preparation without publishing a selection."""


def choose_provider_recovery(error: Exception, *, title: str) -> str | None:
    return run_selection_screen(
        title,
        display_escape_text(str(error)),
        (
            SelectionOption(
                value="login",
                label="Log in",
                description="Open Codex login, then retry.",
            ),
            SelectionOption(
                value="retry",
                label="Retry",
                description="Check again after correcting login or network access.",
            ),
            SelectionOption(
                value="install",
                label="Install / update Codex",
                description=provider_install_description("codex_chatgpt"),
            ),
            SelectionOption(
                value="configure",
                label="Back to configuration",
                description="Choose another model or reasoning setting.",
            ),
        ),
        heading="mem · LLM Provider",
    )


def prepare_codex_catalog(*, install=False, login=False, interactive=True):
    """Return an authenticated catalog without creating an inference turn."""
    while True:
        try:
            try:
                binary = find_provider_binary("codex_chatgpt")
            except QueryProviderError:
                if install:
                    binary = install_provider_runtime("codex_chatgpt")
                elif not interactive:
                    raise
                else:
                    action = run_selection_screen(
                        "INSTALL LLM PROVIDER",
                        provider_install_description("codex_chatgpt"),
                        (
                            SelectionOption(value="install", label="Install Codex"),
                            SelectionOption(value="retry", label="Check again"),
                        ),
                        heading="mem · LLM Provider",
                    )
                    if action is None:
                        raise ProviderPreparationCancelled
                    if action == "retry":
                        continue
                    binary = install_provider_runtime("codex_chatgpt")
            install = False
            if login:
                if not (sys.stdin.isatty() and sys.stdout.isatty()):
                    raise ValueError(
                        "Codex login requires a person at an interactive terminal."
                    )
                login_provider("codex_chatgpt", binary)
                login = False
            with CommandProgress(
                "LLM PROVIDER", "reading Codex model and reasoning choices", total=1
            ):
                return binary, load_codex_configuration_catalog(
                    "codex_chatgpt", binary=binary
                )
        except QueryProviderError as error:
            if not interactive:
                raise
            action = choose_provider_recovery(error, title="MODEL CATALOG")
            if action in {None, "configure"}:
                raise ProviderPreparationCancelled
            login, install = action == "login", action == "install"
            if install:
                install_provider_runtime("codex_chatgpt")
                install = False


def prepare_checked_codex_provider(
    provider_id,
    model=None,
    *,
    reasoning_effort=None,
    install=False,
    login=False,
    interactive=True,
):
    """First use publishes nothing until the chosen draft passes a real probe."""
    from memcommit.application.operations.llm_provider.codex_configuration import (
        require_configurable_provider,
    )

    require_configurable_provider(provider_id)
    while True:
        binary, catalog = prepare_codex_catalog(
            install=install, login=login, interactive=interactive
        )
        install = login = False
        selection = select_codex_configuration(catalog, model, reasoning_effort)
        if interactive:
            action = run_provider_configuration_screen(
                catalog,
                saved_configuration=selection,
                initial_focus="model",
                configuration_action_label="Check and use Codex",
            )
            if action is None:
                raise ProviderPreparationCancelled
            selection = action.configuration
        try:
            with CommandProgress(
                "LLM PROVIDER", "checking provider with a synthetic prompt", total=1
            ):
                return connect_checked_codex_provider(
                    provider_id,
                    selection.model,
                    reasoning_effort=selection.reasoning_effort,
                    binary=binary,
                )
        except QueryProviderError as error:
            if not interactive:
                raise
            action = choose_provider_recovery(error, title="LLM PROVIDER CONNECTION")
            if action is None:
                raise ProviderPreparationCancelled
            model, reasoning_effort = selection.model, selection.reasoning_effort
            login, install = action == "login", action == "install"
