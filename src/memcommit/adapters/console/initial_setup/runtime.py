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
from memcommit.adapters.console.commands.llm_provider.preparation import (
    ProviderPreparationCancelled, prepare_checked_codex_provider,
)
from memcommit.adapters.console.terminal.components.selection.screen import run_selection_screen
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
    needs_first_profile, needs_provider_setup,
)
from memcommit.application.operations.llm_provider.codex_configuration import (
    save_checked_provider,
)
from memcommit.configuration.config import Config
from memcommit.llm_providers.errors import QueryProviderError


class _InitialSetupCancelled(Exception):
    """Raised when the user cancels initial setup before creating a Profile."""


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
    except (_InitialSetupCancelled, ProviderPreparationCancelled):
        typer.echo("Setup paused. Type 'mem' to continue setup.")
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
    interactive = (
        sys.stdin.isatty() and sys.stdout.isatty() and not approve_profile_creation
    )
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
        connected = prepare_checked_codex_provider(
            provider or "codex_chatgpt", model,
            reasoning_effort=reasoning_effort, install=install, login=login,
            interactive=interactive,
        )
        save_checked_provider(connected)
        typer.echo(f"LLM provider ready: {connected.identity.display_name()}")
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
            action = run_selection_screen(
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
