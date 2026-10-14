"""First installation: checked CLI provider, then reviewed folder Profile."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

from memcommit.adapters.console.commands.profile.picker.app import choose_profile
from memcommit.adapters.console.commands.profile.picker.model import ProfilePickerEntry
from memcommit.adapters.console.commands.profile.presentation import (
    render_profile_create_receipt,
)
from memcommit.adapters.console.commands.setup.runtime import (
    find_provider_binary,
    install_provider_runtime,
    login_provider,
    provider_install_description,
)
from memcommit.adapters.console.commands.setup.screen import (
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
from memcommit.application.operations.setup.application import (
    SETUP_PROVIDERS,
    connect_setup_provider,
    load_setup_model_catalog,
    save_checked_provider,
    select_setup_model,
    setup_provider_option,
    setup_status,
)
from memcommit.configuration.config import Config
from memcommit.providers.errors import QueryProviderError


def _cancel() -> None:
    typer.echo("Setup paused. Resume with: mem setup")
    raise typer.Exit(0)


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
                    "Provider login requires a person at a terminal. Run 'mem setup' interactively."
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


def cmd(
    provider: Annotated[
        Optional[str],  # noqa: UP045 - Typer 0.12 requires typing.Optional.
        typer.Option("--provider", help="codex_chatgpt (Codex CLI)"),
    ] = None,
    model: Annotated[
        Optional[str],  # noqa: UP045 - Typer 0.12 requires typing.Optional.
        typer.Option(
            "--model",
            help="Model ID from the Codex catalog; interactive setup shows a picker",
        ),
    ] = None,
    reasoning_effort: Annotated[
        Optional[str],  # noqa: UP045 - Typer 0.12 requires typing.Optional.
        typer.Option(
            "--reasoning-effort",
            help="Supported reasoning setting; defaults to the selected model's default",
        ),
    ] = None,
    name: Annotated[
        Optional[str],  # noqa: UP045 - Typer 0.12 requires typing.Optional.
        typer.Option("--name", help="First Profile name"),
    ] = None,
    root: Annotated[
        Optional[Path],  # noqa: UP045 - Typer 0.12 requires typing.Optional.
        typer.Option(
            "--root",
            help="Folder for the first Profile; defaults to the current folder",
        ),
    ] = None,
    import_files: Annotated[
        bool,
        typer.Option(
            "--import-files/--no-import-files",
            help="Import supported documents in this folder and descendants",
        ),
    ] = True,
    auto_sync: Annotated[
        bool,
        typer.Option(
            "--auto-sync/--no-auto-sync",
            help="Reflect mem changes in managed documents, including future Contexts",
        ),
    ] = True,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help="Approve the explicit Profile setup; requires --provider and --name",
        ),
    ] = False,
    install: Annotated[
        bool,
        typer.Option(
            "--install", help="Install the selected provider CLI when missing (macOS)"
        ),
    ] = False,
    login: Annotated[
        bool,
        typer.Option(
            "--login", help="Open provider-native login before testing the connection"
        ),
    ] = False,
    status: Annotated[
        bool,
        typer.Option(
            "--status", help="Print JSON readiness without inference or Store creation"
        ),
    ] = False,
) -> None:
    """Connect a provider and create/select the first folder Profile."""
    try:
        if status:
            typer.echo(json.dumps(setup_status(), ensure_ascii=False))
            return
        from memcommit.configuration.workspace import workspace_lock

        with workspace_lock():
            _run_setup(
                provider,
                model,
                reasoning_effort,
                name,
                root,
                import_files,
                auto_sync,
                yes,
                install,
                login,
            )
    except (
        OSError,
        ValueError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        subprocess.SubprocessError,
    ) as error:
        typer.echo("Setup error: " + display_escape_text(str(error)), err=True)
        typer.echo("Resume with: mem setup", err=True)
        raise typer.Exit(1) from error


def _run_setup(
    provider,
    model,
    reasoning_effort,
    name,
    root,
    import_files,
    auto_sync,
    yes,
    install,
    login,
) -> None:
    interactive = sys.stdin.isatty() and sys.stdout.isatty() and not yes
    if yes and (provider is None or name is None):
        raise ValueError("--yes requires explicit --provider and --name.")
    if not interactive and not yes:
        raise ValueError(
            "Run setup in a terminal, or pass --provider ID --name NAME --root PATH --yes."
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
        if not yes:
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
