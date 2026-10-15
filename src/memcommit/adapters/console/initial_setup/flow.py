"""First installation: checked CLI provider, then reviewed folder Profile."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer

from memcommit.adapters.console.commands.profile.picker.app import choose_profile
from memcommit.adapters.console.commands.profile.picker.model import ProfilePickerEntry
from memcommit.adapters.console.commands.profile.presentation import (
    render_profile_create_receipt,
)
from memcommit.adapters.console.initial_setup.provider_runtime import (
    find_provider_binary,
    install_provider_runtime,
    login_provider,
    provider_install_description,
)
from memcommit.adapters.console.initial_setup.screen import (
    choose_setup_action,
    choose_setup_model,
)
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.terminal.components.selection.model import (
    SelectionOption,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.application.operations.profile.config import (
    ProfileConfigError,
    load_profile_registry,
)
from memcommit.application.operations.profile.model._storage import ProfileError
from memcommit.application.operations.profile.model.lifecycle import create_profile
from memcommit.application.initial_setup.configuration import (
    SETUP_PROVIDERS,
    connect_setup_provider,
    load_setup_model_catalog,
    save_checked_provider,
    select_setup_model,
    setup_provider_option,
)
from memcommit.configuration.config import Config
from memcommit.providers.errors import QueryProviderError


class _InitialSetupCancelled(Exception):
    """The person paused first-use preparation without creating a Profile."""


def _cancel() -> None:
    typer.echo("Setup paused. Resume by running mem.")
    raise _InitialSetupCancelled


def _connect_provider_interactively(
    provider_id, model, *, reasoning_effort=None, install, login, interactive
):
    binary = None
    selection = None
    while True:
        try:
            binary = find_provider_binary(provider_id)
        except QueryProviderError:
            if not install:
                if not interactive:
                    raise
                action = choose_setup_action(
                    "INSTALL PROVIDER",
                    provider_install_description(provider_id),
                    (
                        SelectionOption(
                            "install",
                            "Install selected provider",
                            "Continue with the official installer.",
                        ),
                        SelectionOption(
                            "retry",
                            "Check again",
                            "Use this after installing the CLI separately.",
                        ),
                    ),
                )
                if action is None:
                    _cancel()
                if action == "retry":
                    continue
            binary = install_provider_runtime(provider_id)
            install = False
        if login:
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError(
                    "Provider login requires a person at a terminal. Run 'mem' interactively."
                )
            login_provider(provider_id, binary)
            login = False
        try:
            phase = "catalog"
            with CommandProgress(
                "setup", "reading Codex model and reasoning choices", total=1
            ):
                catalog = load_setup_model_catalog(provider_id, binary=binary)
            if selection is None:
                if model is not None:
                    select_setup_model(catalog, model, reasoning_effort)
                if interactive:
                    initial_model = model or Config().model_for_provider(provider_id)
                    if reasoning_effort is not None:
                        available_initial_model = (
                            initial_model
                            if any(option.model == initial_model for option in catalog)
                            else None
                        )
                        initial_model = select_setup_model(
                            catalog, available_initial_model, reasoning_effort
                        ).model
                    selection = choose_setup_model(
                        catalog,
                        initial_model=initial_model,
                        initial_reasoning_effort=reasoning_effort
                        or (
                            Config().get("codex_chatgpt_reasoning_effort")
                            if model is None
                            or model == Config().model_for_provider(provider_id)
                            else None
                        ),
                    )
                    if selection is None:
                        return None
                else:
                    selection = select_setup_model(catalog, model, reasoning_effort)
            else:
                select_setup_model(catalog, selection.model, selection.reasoning_effort)
            phase = "probe"
            with CommandProgress(
                "setup", "checking provider with a synthetic prompt", total=1
            ):
                return connect_setup_provider(
                    provider_id,
                    selection.model,
                    reasoning_effort=selection.reasoning_effort,
                    binary=binary,
                )
        except QueryProviderError as error:
            if not interactive:
                raise
            action = choose_setup_action(
                "MODEL CATALOG" if phase == "catalog" else "PROVIDER CONNECTION",
                display_escape_text(str(error)),
                (
                    SelectionOption(
                        "login",
                        "Log in",
                        "Open the provider CLI login, then repeat the connection test.",
                    ),
                    SelectionOption(
                        "retry",
                        "Retry connection",
                        "Use this after correcting login or network access.",
                    ),
                    SelectionOption(
                        "install",
                        "Install / update Codex",
                        provider_install_description(provider_id),
                    ),
                    SelectionOption(
                        "model",
                        "Back to provider"
                        if phase == "catalog"
                        else "Choose model / reasoning again",
                        "Return to setup choices."
                        if phase == "catalog"
                        else "Change the model or reasoning setting, then check the connection.",
                    ),
                ),
            )
            if action is None:
                _cancel()
            if action == "model":
                if phase == "catalog":
                    return None
                model, reasoning_effort = selection.model, selection.reasoning_effort
                selection = None
                continue
            login = action == "login"
            if action == "install":
                binary = install_provider_runtime(provider_id)


def run_initial_setup(
    *,
    provider: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    name: str | None = None,
    root: Path | None = None,
    import_files: bool = True,
    auto_sync: bool = True,
    approve_profile_creation: bool = False,
    install: bool = False,
    login: bool = False,
) -> int:
    """Run first-use preparation from the console entry point, not a command."""
    from memcommit.configuration.workspace import WorkspaceError, workspace_lock

    try:
        with workspace_lock():
            _run_initial_setup(
                provider,
                model,
                reasoning_effort,
                name,
                root,
                import_files,
                auto_sync,
                approve_profile_creation,
                install,
                login,
            )
    except _InitialSetupCancelled:
        return 0
    except (
        OSError,
        ValueError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        WorkspaceError,
        subprocess.SubprocessError,
    ) as error:
        typer.echo("Setup error: " + display_escape_text(str(error)), err=True)
        typer.echo("Resume by running mem.", err=True)
        return 1
    return 0


def _run_initial_setup(
    provider,
    model,
    reasoning_effort,
    name,
    root,
    import_files,
    auto_sync,
    approve_profile_creation,
    install,
    login,
) -> None:
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not approve_profile_creation
    if approve_profile_creation and (provider is None or name is None):
        raise ValueError("Approved Profile creation requires an explicit provider and Profile name.")
    if not interactive and not approve_profile_creation:
        raise ValueError(
            "Run mem in a terminal to complete initial setup."
        )
    registry = load_profile_registry()
    first_profile_needed = registry.generation == 0
    while True:
        if provider is None:
            chosen = choose_setup_action(
                "PROVIDER",
                "Choose the CLI used for mem's semantic operations. Login stays with that CLI.",
                tuple(
                    SelectionOption(
                        option.uid,
                        option.label,
                        f"{option.command} headless · model choices are read after login",
                    )
                    for option in SETUP_PROVIDERS
                ),
                initial_uid=Config().get("semantic_provider"),
            )
            if chosen is None:
                _cancel()
            provider = chosen
        setup_provider_option(provider)
        connected = _connect_provider_interactively(
            provider,
            model,
            reasoning_effort=reasoning_effort,
            install=install,
            login=login,
            interactive=interactive,
        )
        if connected is not None:
            break
        provider = model = reasoning_effort = None
    save_checked_provider(connected)
    typer.echo(f"Provider ready: {connected.identity.display_name()}")
    if not first_profile_needed:
        Config().update({"setup_complete": True})
        typer.echo(f"Setup complete. Active Profile: {registry.active.name}")
        return
    if name is not None:
        profile_root = (root or Path.cwd()).expanduser().resolve()
        from memcommit.application.operations.profile.project_documents import (
            prepare_project_import,
        )

        prepared = prepare_project_import(profile_root) if import_files else None
        digest = prepared.digest if prepared else None
        if not approve_profile_creation:
            action = choose_setup_action(
                "FIRST PROFILE",
                f"Create {name} in {profile_root}. Import {len(prepared.files) if prepared else 0} documents. Auto Sync {'ON' if auto_sync else 'OFF'}.",
                (
                    SelectionOption(
                        "create",
                        "Create and use this folder Profile",
                        "Applies to this folder and its subfolders.",
                    ),
                ),
            )
            if action is None:
                _cancel()
    else:
        # Reuse the existing reviewed creation screen without inspecting or
        # creating the virtual authoring Store during first installation.
        action = choose_profile(
            tuple(
                ProfilePickerEntry(
                    item.name, 0, None, uid=item.uid, root_dir=item.root_dir
                )
                for item in registry.profiles
            ),
            current=registry.active.name,
            registry_generation=registry.generation,
            start_create=True,
            select_created=True,
            initial_root=str(root.expanduser().resolve())
            if root
            else str(Path.home() / "mem")
            if Path.cwd() == Path.home()
            else None,
        )
        if action is None:
            _cancel()
        name, profile_root = action.name, Path(action.root_dir)
        import_files, auto_sync, digest = (
            action.import_project_files,
            action.automatic_sync,
            action.import_digest,
        )
    result = create_profile(
        name,
        root_dir=profile_root,
        expected_generation=registry.generation,
        import_project_files=import_files,
        automatic_sync=auto_sync,
        expected_import_digest=digest,
        select_created=True,
    )
    render_profile_create_receipt(result)
    Config().update({"setup_complete": True})
    typer.echo(
        "Setup complete. mem uses the selected Profile until you select another one."
    )
    typer.echo("For another folder: cd PATH, run mem profile, then choose New Profile.")
    typer.echo(
        "This Profile manages this folder and its subfolders. mem init NAME creates a Context inside it."
    )
