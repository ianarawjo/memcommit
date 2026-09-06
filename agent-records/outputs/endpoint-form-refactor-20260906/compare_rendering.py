"""Compare baseline and refactored form cells through real prompt-toolkit input."""

from __future__ import annotations
import asyncio
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
from unittest.mock import patch
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
from memcommit.adapters.console.terminal.components.endpoint_setup.model import (
    EndpointSetupMemory,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.command_binding import (
    EndpointCommandBinding,
)
from memcommit.adapters.console.terminal.components.endpoint_setup.form.screen import (
    _EndpointSetupForm,
)
from memcommit.adapters.console.commands.meld import endpoint_setup as meld
from memcommit.adapters.console.commands.branch import endpoint_setup as branch
from memcommit.adapters.console.commands.update.workbench import setup as update
from memcommit.adapters.console.commands.update.workbench.model import (
    UpdateEndpointSetup,
)
from memcommit.adapters.console.commands.reference import endpoint_setup as reference
from memcommit.adapters.console.commands.reference import (
    command_codec as reference_codec,
)

REPOSITORY = Path(__file__).resolve().parents[3]
BASE_REVISION = "0d7ff831860c4e0d59faa83378ed216aa0757e7d"
BASE_PACKAGE = (
    "src/memcommit/adapters/console/terminal/components/endpoint_setup/compact"
)
HERE = Path(tempfile.mkdtemp(prefix="endpoint-form-render-"))
OUTPUT = Path(__file__).with_name("render-comparison.json")
UIDS = ("abcd1234-0000-4000-8000-000000000000", "bcde2345-0000-4000-8000-000000000000")


class SizedOutput(DummyOutput):
    def get_size(self):
        return Size(rows=52, columns=180)

    def get_rows_below_cursor_position(self):
        return 52


def memories(role_uid, context_name):
    return tuple(
        EndpointSetupMemory(
            context_name, uid, f"{role_uid} evidence {i} in {context_name}."
        )
        for i, uid in enumerate(UIDS, 1)
    )


def capture_arguments(module, call):
    with patch.object(module, "run_endpoint_setup", return_value=None) as launch:
        call()
    args, kwargs = launch.call_args
    kwargs.pop("require_tty", None)
    kwargs.pop("app_input", None)
    kwargs.pop("app_output", None)
    kwargs.setdefault("memory_loader", None)
    return args[0], kwargs


def scenarios():
    meld_setup = meld.MeldTuiSetup(
        names=("meld/a", "meld/b", "meld/empty"),
        left_name="meld/a",
        right_name="meld/b",
        eligible_target_names=frozenset({"meld/empty"}),
        current_context="meld/a",
    )
    meld_spec, meld_args = capture_arguments(
        meld,
        lambda: meld.choose_meld_endpoint_setup(
            meld_setup, memory_loader=memories, require_tty=False
        ),
    )
    branch_spec, branch_args = capture_arguments(
        branch,
        lambda: branch.choose_branch_creation(
            ("alpha", "beta"),
            current="alpha",
            suggest_name=lambda source: source + "/branch",
            validate_name=lambda name: None,
            require_tty=False,
        ),
    )
    update_setup = UpdateEndpointSetup(
        names=("alpha", "beta"),
        source_name="alpha",
        target_name="beta",
        current_context="alpha",
    )
    update_spec, update_args = capture_arguments(
        update,
        lambda: update.choose_update_endpoint_setup(
            update_setup, memory_loader=memories, require_tty=False
        ),
    )
    reference_spec = reference.reference_endpoint_setup_spec(
        reference.ReferenceTuiSetup(
            names=("workspace",),
            selected_source="shared/source",
            selected_target="workspace",
            current_context="workspace",
            memory_source_names=("shared/source", "workspace"),
            memory_source_selectable_names=frozenset({"shared/source", "workspace"}),
            selected_memory_source="shared/source",
        )
    )
    reference_args = dict(
        memory_loader=memories,
        validate_draft=reference._validate_reference_draft,
        command_editor=EndpointCommandBinding(
            form=reference_codec.REFERENCE_COMMAND_FORM,
            review=reference_codec.build_review,
            parse=reference_codec.parse_endpoint_argv,
        ),
    )

    def fail(_role, _name):
        raise ValueError("Frozen Memory projection unavailable.")

    preview_spec = replace(
        update_spec,
        roles=(
            replace(
                update_spec.roles[0],
                allow_inline_memory=False,
                memory_preview_only=True,
            ),
            update_spec.roles[1],
        ),
    )
    down = "\x1b[B"
    right = "\x1b[C"
    left = "\x1b[D"
    enter = "\r"
    esc = "\x1b"
    tab = "\t"
    return [
        (
            "meld-stored",
            meld_spec,
            meld_args,
            [
                right,
                down,
                right,
                down,
                right,
                enter,
                down,
                enter,
                right,
                enter,
                down,
                enter,
                down,
                "\x15meld/a",
                down,
                enter,
            ],
        ),
        (
            "meld-symmetric",
            meld_spec,
            meld_args,
            [
                down,
                right,
                right,
                " ",
                down,
                right,
                right,
                " ",
                down,
                "meld/new-result",
                enter,
                enter,
            ],
        ),
        (
            "update-inline-command",
            update_spec,
            update_args,
            [
                right,
                right,
                down,
                enter,
                "Exact inline evidence.",
                enter,
                down,
                "\x15invalid-context --into beta",
                enter,
                "\x15--memory Inline --to beta",
                enter,
                esc,
            ],
        ),
        (
            "branch-parent-command",
            branch_spec,
            branch_args,
            [
                down,
                "\x15alpha/custom",
                right,
                enter,
                down,
                enter,
                left,
                down,
                "\x15beta --from alpha --source-root-only",
                enter,
                "\x15beta/final --from alpha --source-root-only",
                enter,
            ],
        ),
        (
            "reference-required",
            reference_spec,
            reference_args,
            [down, "\x15shared/source:abcd", enter, enter, down, enter, down, enter],
        ),
        (
            "update-load-failure",
            update_spec,
            {**update_args, "memory_loader": fail},
            [right, down, right, right, enter, esc],
        ),
        (
            "preview-read-only",
            preview_spec,
            {**update_args, "command_editor": None},
            [right, right, right, enter, down, enter, left, down, down, enter],
        ),
        (
            "browser-cancel-completion",
            branch_spec,
            branch_args,
            [right, enter, down, esc, left, "\x15b", esc, esc],
        ),
    ]


def baseline_class():
    baseline = HERE / "baseline"
    baseline.mkdir()
    for name in ("__init__.py", "screen.py", "endpoint_editor.py", "command_sync.py"):
        source = subprocess.run(
            ["git", "show", f"{BASE_REVISION}:{BASE_PACKAGE}/{name}"],
            cwd=REPOSITORY,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        (baseline / name).write_text(source)
    name = "_endpoint_form_baseline"
    module_spec = importlib.util.spec_from_file_location(
        name,
        HERE / "baseline" / "__init__.py",
        submodule_search_locations=[str(HERE / "baseline")],
    )
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[name] = module
    module_spec.loader.exec_module(module)
    return importlib.import_module(name + ".screen")._CompactEndpointScreen


def cell_state(app):
    rendered = app.renderer.last_rendered_screen
    cells = [
        [
            (rendered.data_buffer[y][x].char, rendered.data_buffer[y][x].style)
            for x in range(180)
        ]
        for y in range(52)
    ]
    return dict(
        cells=cells,
        cursor=[
            rendered.get_cursor_position(app.layout.current_window).x,
            rendered.get_cursor_position(app.layout.current_window).y,
        ],
    )


async def run_path(cls, spec, kwargs, keys):
    states = []
    with create_pipe_input() as pipe:
        form = cls(spec, **kwargs, app_input=pipe, app_output=SizedOutput())
        app = form.app
        task = asyncio.create_task(app.run_async())
        try:
            await asyncio.sleep(0.06)
            states.append(cell_state(app))
            for key in keys:
                if task.done():
                    break
                pipe.send_text(key)
                await asyncio.sleep(0.06)
                if not task.done():
                    states.append(cell_state(app))
            if not task.done():
                pipe.send_text("\x03")
            result = await asyncio.wait_for(task, 2)
            return states, asdict(result) if result is not None else None
        finally:
            if not task.done():
                app.exit(result=None)
                await task


async def main():
    old = baseline_class()
    summary = []
    total = 0
    for name, spec, kwargs, keys in scenarios():
        before, result_before = await run_path(old, spec, kwargs, keys)
        after, result_after = await run_path(_EndpointSetupForm, spec, kwargs, keys)
        assert len(before) == len(after), (name, "state-count", len(before), len(after))
        for index, (left, right) in enumerate(zip(before, after)):
            if left != right:
                (HERE / f"{name}-{index}-before.json").write_text(
                    json.dumps(left, ensure_ascii=False)
                )
                (HERE / f"{name}-{index}-after.json").write_text(
                    json.dumps(right, ensure_ascii=False)
                )
                raise AssertionError((name, index, "render differs"))
        assert result_before == result_after, (
            name,
            "draft differs",
            result_before,
            result_after,
        )
        if name not in {"update-load-failure", "browser-cancel-completion"}:
            assert result_after is not None, (name, "expected a completed draft")
        summary.append(
            dict(
                path=name,
                states=len(before),
                keys=keys,
                result=result_after,
                cell_sha256=[
                    hashlib.sha256(
                        json.dumps(s, ensure_ascii=False).encode()
                    ).hexdigest()
                    for s in after
                ],
            )
        )
        total += len(before)
        print(name, len(before), "states, identical cells/cursor/draft", flush=True)
    report = dict(
        baseline_revision=BASE_REVISION,
        baseline_package=BASE_PACKAGE,
        viewport=dict(columns=180, rows=52),
        total_states=total,
        paths=summary,
    )
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"{total} total states match.")


if __name__ == "__main__":
    asyncio.run(main())
