"""Contracts for the rebuilt operation-neutral endpoint setup component."""

from __future__ import annotations

from prompt_toolkit.input.defaults import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

from memcommit.adapters.interfaces.tui.components.endpoint_setup import (
    EndpointSetupDraft,
    EndpointSetupMemory,
    EndpointSetupMode,
    EndpointSetupRole,
    EndpointSetupSpec,
    EndpointSetupValue,
    run_endpoint_setup,
)


def _spec() -> EndpointSetupSpec:
    return EndpointSetupSpec(
        title="NEW TEST OPERATION",
        subtitle="CHOOSE SHAPE AND ENDPOINTS WITHOUT MUTATION",
        modes=(
            EndpointSetupMode("DIRECT", "DIRECT · A → B", "Exact roots only."),
            EndpointSetupMode(
                "RECURSIVE",
                "RECURSIVE · A/** → B/**",
                "Match descendants by relative path.",
            ),
        ),
        initial_mode_uid="DIRECT",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "target"),
                frozenset({"source"}),
                "source",
                current_context="target",
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target",),
                frozenset({"target"}),
                "target",
                current_context="target",
                fixed=True,
            ),
        ),
    )


def test_endpoint_setup_returns_default_shape_and_frozen_target() -> None:
    with create_pipe_input() as pipe_input:
        # A multi-mode setup starts on Operation Shape; Source and Continue
        # are the next two visible focus surfaces.
        pipe_input.send_text("\t\t\r")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned == EndpointSetupDraft(
        "DIRECT",
        (
            EndpointSetupValue("A", "source"),
            EndpointSetupValue("B", "target"),
        ),
    )


def test_endpoint_setup_switches_coupled_operation_shape() -> None:
    with create_pipe_input() as pipe_input:
        # Operation Shape owns first focus. Right stages Recursive and two
        # Tabs cross Source to Continue; the frozen target is not a focus stop.
        pipe_input.send_text("\x1b[C\t\t\r")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.mode_uid == "RECURSIVE"
    assert returned.value("B").context_name == "target"


def test_endpoint_setup_cancel_returns_no_draft() -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("q")
        returned = run_endpoint_setup(
            _spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None


def _independent_reach_spec() -> EndpointSetupSpec:
    return EndpointSetupSpec(
        title="NEW RANGE OPERATION",
        subtitle="CHOOSE EACH ENDPOINT RANGE INDEPENDENTLY",
        modes=(EndpointSetupMode("RANGE", "A → B"),),
        initial_mode_uid="RANGE",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "source/child"),
                frozenset({"source", "source/child"}),
                "source",
                allow_descendants=True,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target", "target/child"),
                frozenset({"target", "target/child"}),
                "target",
                allow_descendants=True,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("keys", "source_descendants", "target_descendants"),
    (
        ("\t\t\t\t\r", False, False),
        ("\t\x1b[C\t\t\t\r", True, False),
        ("\t\t\t\x1b[C\t\r", False, True),
        ("\t\x1b[C\t\t\x1b[C\t\r", True, True),
    ),
)
def test_endpoint_setup_freezes_each_role_range_independently(
    keys: str,
    source_descendants: bool,
    target_descendants: bool,
) -> None:
    with create_pipe_input() as pipe_input:
        pipe_input.send_text(keys)
        returned = run_endpoint_setup(
            _independent_reach_spec(),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A").include_descendants is source_descendants
    assert returned.value("B").include_descendants is target_descendants


def test_endpoint_setup_rejects_hidden_initial_descendant_state() -> None:
    with pytest.raises(ValueError, match="without a range control"):
        EndpointSetupRole(
            "A",
            "A",
            ("source",),
            frozenset({"source"}),
            "source",
            include_descendants=True,
        )


def test_endpoint_setup_read_only_memory_preview_requires_a_memory_control() -> None:
    with pytest.raises(ValueError, match="read-only Memory preview"):
        EndpointSetupRole(
            "A",
            "A",
            ("source",),
            frozenset({"source"}),
            "source",
            memory_preview_only=True,
        )


def test_endpoint_setup_preserves_an_explicit_initial_role_range() -> None:
    spec = _independent_reach_spec()
    source, target = spec.roles
    spec = EndpointSetupSpec(
        title=spec.title,
        subtitle=spec.subtitle,
        modes=spec.modes,
        initial_mode_uid=spec.initial_mode_uid,
        roles=(
            EndpointSetupRole(
                source.uid,
                source.label,
                source.names,
                source.selectable_names,
                source.selected_name,
                allow_descendants=True,
                include_descendants=True,
            ),
            target,
        ),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\t\r")
        returned = run_endpoint_setup(
            spec,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A").include_descendants is True
    assert returned.value("B").include_descendants is False


def test_endpoint_setup_validator_receives_both_exact_role_ranges() -> None:
    observed: list[tuple[bool, bool]] = []

    def validate(draft: EndpointSetupDraft) -> str | None:
        ranges = (
            draft.value("A").include_descendants,
            draft.value("B").include_descendants,
        )
        observed.append(ranges)
        return "Target descendants are unavailable." if ranges[1] else None

    with create_pipe_input() as pipe_input:
        # Select only B descendants, attempt Continue, then cancel after the
        # operation-owned validator keeps the setup open.
        pipe_input.send_text("\t\t\t\x1b[C\t\rq")
        returned = run_endpoint_setup(
            _independent_reach_spec(),
            validate_draft=validate,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert observed == [(False, True)]


def _memory_focus_spec() -> EndpointSetupSpec:
    return EndpointSetupSpec(
        title="MEMORY FOCUS OPERATION",
        subtitle="CHOOSE AN EXACT CONTEXT OR ONE DIRECT MEMORY",
        modes=(EndpointSetupMode("FOCUS", "A → RESULT"),),
        initial_mode_uid="FOCUS",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source", "target"),
                frozenset({"source", "target"}),
                "source",
                allow_descendants=True,
                allow_memory_focus=True,
                memory_height=8,
            ),
        ),
    )


def _memory_focus_loader(
    _role_uid: str,
    context_name: str,
) -> tuple[EndpointSetupMemory, ...]:
    memories = (
        EndpointSetupMemory(
            "source",
            "11111111-1111-4111-8111-111111111111",
            "First Source Memory.",
        ),
        EndpointSetupMemory(
            "source",
            "22222222-2222-4222-8222-222222222222",
            "Second Source Memory.",
        ),
        EndpointSetupMemory(
            "target",
            "33333333-3333-4333-8333-333333333333",
            "Target Memory.",
        ),
    )
    return tuple(memory for memory in memories if memory.context_name == context_name)


def test_endpoint_setup_returns_one_exact_memory_focus() -> None:
    with create_pipe_input() as pipe_input:
        # Context -> Range -> Memory Focus -> first direct Memory -> Continue.
        pipe_input.send_text("\t\t\x1b[B\r\t\r")
        returned = run_endpoint_setup(
            _memory_focus_spec(),
            memory_loader=_memory_focus_loader,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue(
        "A",
        "source",
        include_descendants=False,
        memory_uid="11111111-1111-4111-8111-111111111111",
    )


def test_endpoint_setup_read_only_memory_preview_cannot_enter_the_draft() -> None:
    base = _memory_focus_spec()
    source = base.roles[0]
    spec = EndpointSetupSpec(
        title=base.title,
        subtitle=base.subtitle,
        modes=base.modes,
        initial_mode_uid=base.initial_mode_uid,
        roles=(
            EndpointSetupRole(
                source.uid,
                source.label,
                source.names,
                source.selectable_names,
                source.selected_name,
                allow_descendants=True,
                allow_memory_focus=True,
                memory_preview_only=True,
                memory_height=8,
            ),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Context -> Range -> read-only Memory evidence. Move to one Memory and
        # press Enter, then continue; the cursor must not become a typed UID.
        pipe_input.send_text("\t\t\x1b[B\r\t\r")
        returned = run_endpoint_setup(
            spec,
            memory_loader=_memory_focus_loader,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue("A", "source")


def test_endpoint_setup_descendant_reach_clears_memory_focus_immediately() -> None:
    with create_pipe_input() as pipe_input:
        # Select one Memory, return to Range, choose descendants, then cross the
        # visibly disabled Memory Focus frame and continue.
        pipe_input.send_text("\t\t\x1b[B\r\x1b[Z\x1b[C\t\t\r")
        returned = run_endpoint_setup(
            _memory_focus_spec(),
            memory_loader=_memory_focus_loader,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue(
        "A",
        "source",
        include_descendants=True,
        memory_uid=None,
    )


def test_endpoint_setup_context_choice_clears_memory_focus() -> None:
    with create_pipe_input() as pipe_input:
        # Select a Source Memory, return through Range to Context, choose the
        # other exact Context, then continue with its whole frame.
        pipe_input.send_text("\t\t\x1b[B\r\x1b[Z\x1b[Z\x1b[B\r\t\t\t\r")
        returned = run_endpoint_setup(
            _memory_focus_spec(),
            memory_loader=_memory_focus_loader,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue(
        "A",
        "target",
        include_descendants=False,
        memory_uid=None,
    )


def test_endpoint_setup_loads_memory_projections_only_for_chosen_contexts() -> None:
    loaded: list[tuple[str, str]] = []

    def load(role_uid: str, context_name: str):
        loaded.append((role_uid, context_name))
        return _memory_focus_loader(role_uid, context_name)

    with create_pipe_input() as pipe_input:
        # Initial Source is loaded for its visible frame. Moving the Context
        # cursor does not load Target; explicit selection does.
        pipe_input.send_text("\x1b[B\rq")
        returned = run_endpoint_setup(
            _memory_focus_spec(),
            memory_loader=load,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is None
    assert loaded == [("A", "source"), ("A", "target")]


def test_endpoint_setup_does_not_load_memories_for_initial_descendant_reach() -> None:
    loaded: list[tuple[str, str]] = []
    role = _memory_focus_spec().roles[0]
    spec = EndpointSetupSpec(
        title="INITIAL SUBTREE",
        subtitle="MEMORY FOCUS IS DISABLED",
        modes=(EndpointSetupMode("FOCUS", "A → RESULT"),),
        initial_mode_uid="FOCUS",
        roles=(
            EndpointSetupRole(
                role.uid,
                role.label,
                role.names,
                role.selectable_names,
                role.selected_name,
                allow_descendants=True,
                include_descendants=True,
                allow_memory_focus=True,
            ),
        ),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\r")
        returned = run_endpoint_setup(
            spec,
            memory_loader=lambda role_uid, context_name: loaded.append(
                (role_uid, context_name)
            )
            or (),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue(
        "A",
        "source",
        include_descendants=True,
    )
    assert loaded == []


def test_endpoint_setup_clears_only_the_role_broadened_to_descendants() -> None:
    source_uid = "11111111-1111-4111-8111-111111111111"
    target_uid = "33333333-3333-4333-8333-333333333333"
    spec = EndpointSetupSpec(
        title="TWO ROLE MEMORY FOCUS",
        subtitle="KEEP EACH ROLE INDEPENDENT",
        modes=(EndpointSetupMode("FOCUS", "A → B"),),
        initial_mode_uid="FOCUS",
        roles=(
            EndpointSetupRole(
                "A",
                "A · SOURCE",
                ("source",),
                frozenset({"source"}),
                "source",
                allow_descendants=True,
                allow_memory_focus=True,
            ),
            EndpointSetupRole(
                "B",
                "B · TARGET",
                ("target",),
                frozenset({"target"}),
                "target",
                allow_descendants=True,
                allow_memory_focus=True,
            ),
        ),
    )

    with create_pipe_input() as pipe_input:
        # Focus one Memory in each role, then broaden B only. A must remain an
        # exact focused Memory while B becomes a whole subtree.
        pipe_input.send_text("\t\t\x1b[B\r\t\t\t\x1b[B\r\x1b[Z\x1b[C\t\t\r")
        returned = run_endpoint_setup(
            spec,
            memory_loader=lambda _role_uid, context_name: (
                EndpointSetupMemory(context_name, source_uid, "Source Memory."),
            )
            if context_name == "source"
            else (EndpointSetupMemory(context_name, target_uid, "Target Memory."),),
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A") == EndpointSetupValue(
        "A",
        "source",
        memory_uid=source_uid,
    )
    assert returned.value("B") == EndpointSetupValue(
        "B",
        "target",
        include_descendants=True,
    )


def test_endpoint_setup_preserves_explicit_initial_memory_focus() -> None:
    spec = _memory_focus_spec()
    role = spec.roles[0]
    selected_uid = "22222222-2222-4222-8222-222222222222"
    spec = EndpointSetupSpec(
        title=spec.title,
        subtitle=spec.subtitle,
        modes=spec.modes,
        initial_mode_uid=spec.initial_mode_uid,
        roles=(
            EndpointSetupRole(
                role.uid,
                role.label,
                role.names,
                role.selectable_names,
                role.selected_name,
                allow_descendants=True,
                allow_memory_focus=True,
                selected_memory_uid=selected_uid,
                memory_height=role.memory_height,
            ),
        ),
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\t\t\t\r")
        returned = run_endpoint_setup(
            spec,
            memory_loader=_memory_focus_loader,
            app_input=pipe_input,
            app_output=DummyOutput(),
            require_tty=False,
        )

    assert returned is not None
    assert returned.value("A").memory_uid == selected_uid


def test_endpoint_setup_rejects_hidden_or_incompatible_memory_focus() -> None:
    memory = EndpointSetupMemory("source", "11111111", "Memory.")
    with pytest.raises(ValueError, match="projection loader"):
        run_endpoint_setup(
            _memory_focus_spec(),
            app_output=DummyOutput(),
            require_tty=False,
        )
    with pytest.raises(ValueError, match="outside its selected Context"):
        spec = _memory_focus_spec()
        role = spec.roles[0]
        run_endpoint_setup(
            EndpointSetupSpec(
                title=spec.title,
                subtitle=spec.subtitle,
                modes=spec.modes,
                initial_mode_uid=spec.initial_mode_uid,
                roles=(
                    EndpointSetupRole(
                        role.uid,
                        role.label,
                        role.names,
                        role.selectable_names,
                        "target",
                        allow_descendants=True,
                        allow_memory_focus=True,
                        selected_memory_uid=memory.uid,
                    ),
                ),
            ),
            memory_loader=_memory_focus_loader,
            app_output=DummyOutput(),
            require_tty=False,
        )
    with pytest.raises(ValueError, match="combine Memory focus"):
        EndpointSetupRole(
            "A",
            "A",
            ("source",),
            frozenset({"source"}),
            "source",
            allow_descendants=True,
            include_descendants=True,
            allow_memory_focus=True,
            selected_memory_uid=memory.uid,
        )
    with pytest.raises(ValueError, match="cannot focus one Memory"):
        EndpointSetupValue(
            "A",
            "source",
            include_descendants=True,
            memory_uid=memory.uid,
        )


def test_endpoint_setup_rejects_invalid_memory_loader_projections() -> None:
    with create_pipe_input() as pipe_input:
        with pytest.raises(ValueError, match="another Context"):
            run_endpoint_setup(
                _memory_focus_spec(),
                memory_loader=lambda _role_uid, _context_name: (
                    EndpointSetupMemory("target", "11111111", "Wrong owner."),
                ),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
    duplicate = EndpointSetupMemory("source", "11111111", "Duplicate.")
    with create_pipe_input() as pipe_input:
        with pytest.raises(ValueError, match="duplicate UIDs"):
            run_endpoint_setup(
                _memory_focus_spec(),
                memory_loader=lambda _role_uid, _context_name: (
                    duplicate,
                    duplicate,
                ),
                app_input=pipe_input,
                app_output=DummyOutput(),
                require_tty=False,
            )
