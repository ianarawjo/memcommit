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
from memcommit.adapters.console.initial_setup.provider_setup import (
    find_provider_binary,
    install_provider_runtime,
    login_provider,
    provider_install_description,
)
from memcommit.adapters.console.initial_setup.screen import (
    run_setup_selection_screen,
    run_setup_model_selection_screen,
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
    needs_first_profile,
    needs_provider_setup,
    save_checked_provider,
    select_setup_model,
    setup_provider_option,
)
from memcommit.configuration.config import Config
from memcommit.providers.errors import QueryProviderError
from memcommit.providers.profile_routes import ProfileProviderRoutesError


class _InitialSetupCancelled(Exception):
    """Raised when the user cancels initial setup before creating a Profile."""


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
                action = run_setup_selection_screen(
                    "INSTALL PROVIDER",
                    provider_install_description(provider_id),
                    (
                        SelectionOption(
                            value="install",
                            label="Install selected provider",
                            description="Continue with the official installer.",
                        ),
                        SelectionOption(
                            value="retry",
                            label="Check again",
                            description="Use this after installing the CLI separately.",
                        ),
                    ),
                )
                if action is None:
                    raise _InitialSetupCancelled
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
                if interactive:
                    if model is not None or reasoning_effort is not None:
                        model = select_setup_model(
                            catalog=catalog,
                            model=model,
                            reasoning_effort=reasoning_effort,
                        ).model
                    selection = run_setup_model_selection_screen(
                        catalog,
                        last_selected_model=model,
                        last_selected_reasoning_effort=reasoning_effort,
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
            action = run_setup_selection_screen(
                "MODEL CATALOG" if phase == "catalog" else "PROVIDER CONNECTION",
                display_escape_text(str(error)),
                (
                    SelectionOption(
                        value="login",
                        label="Log in",
                        description="Open the provider CLI login, then repeat the connection test.",
                    ),
                    SelectionOption(
                        value="retry",
                        label="Retry connection",
                        description="Use this after correcting login or network access.",
                    ),
                    SelectionOption(
                        value="install",
                        label="Install / update Codex",
                        description=provider_install_description(provider_id),
                    ),
                    SelectionOption(
                        value="model",
                        label="Back to provider"
                        if phase == "catalog"
                        else "Choose model / reasoning again",
                        description="Return to setup choices."
                        if phase == "catalog"
                        else "Change the model or reasoning setting, then check the connection.",
                    ),
                ),
            )
            if action is None:
                raise _InitialSetupCancelled
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
    approve_profile_creation: bool = False,
    install: bool = False,
    login: bool = False,
) -> int:
    """Run first-use preparation from the console entry point, not a command."""
    from memcommit.configuration.workspace import WorkspaceError

    try:
        _run_initial_setup(
            provider,
            model,
            reasoning_effort,
            name,
            root,
            import_files,
            approve_profile_creation,
            install,
            login,
        )
    except _InitialSetupCancelled:
        typer.echo("Setup paused. Type 'mem' to continue setup.")
        return 0
    except (
        OSError,
        ValueError,
        ProfileConfigError,
        ProfileError,
        ProfileProviderRoutesError,
        QueryProviderError,
        WorkspaceError,
        subprocess.SubprocessError,
    ) as error:
        typer.echo("Setup error: " + display_escape_text(str(error)), err=True)
        typer.echo("Type 'mem' to continue setup.", err=True)
        return 1
    return 0


def _run_initial_setup(
    provider,
    model,
    reasoning_effort,
    name,
    root,
    import_files,
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
    first_profile_needed = needs_first_profile()
    # Explicit internal creation may add a folder beside legacy authoring data.
    if name is not None and registry.generation == 0:
        first_profile_needed = True
    provider_setup_requested = (
        provider is not None
        or model is not None
        or reasoning_effort is not None
        or install
        or login
    )
    if provider_setup_requested or needs_provider_setup():
        while True:
            if provider is None:
                chosen = run_setup_selection_screen(
                    "PROVIDER",
                    "Choose the CLI used for mem's semantic operations. Login stays with that CLI.",
                    tuple(
                        SelectionOption(
                            value=option.uid,
                            label=option.label,
                            description=f"{option.command} headless · model choices are read after login",
                        )
                        for option in SETUP_PROVIDERS
                    ),
                )
                if chosen is None:
                    raise _InitialSetupCancelled
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
            action = run_setup_selection_screen(
                "FIRST PROFILE",
                f"Create {name} in {profile_root}. Import {len(prepared.files) if prepared else 0} documents.",
                (
                    SelectionOption(
                        value="create",
                        label="Create and use this folder Profile",
                        description="Applies to this folder and its subfolders.",
                    ),
                ),
            )
            if action is None:
                raise _InitialSetupCancelled
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
            raise _InitialSetupCancelled
        name, profile_root = action.name, Path(action.root_dir)
        import_files, digest = action.import_project_files, action.import_digest
    result = create_profile(
        name,
        root_dir=profile_root,
        expected_generation=registry.generation,
        import_project_files=import_files,
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
