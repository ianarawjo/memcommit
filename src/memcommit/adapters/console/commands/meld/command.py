"""Stable import facade for the responsibility-split Meld command."""

import sys as _sys
from types import ModuleType as _ModuleType

from memcommit.adapters.console.commands.meld import entrypoint as _entrypoint
from memcommit.adapters.console.commands.meld import interpretation as _interpretation
from memcommit.adapters.console.commands.meld import presentation as _presentation
from memcommit.adapters.console.commands.meld.workflow import workflow as _workflow

from memcommit.adapters.console.commands.meld.errors import MeldCommandError
from memcommit.adapters.console.commands.meld.interpretation import (
    InterpretedMeldCommand,
    MeldCommandInterpretationError,
    MeldCommandRequest,
    MeldSessionsCommand,
    MeldSetupCommand,
    _is_inline_memory_operand,
    interpret_meld_command,
)
from memcommit.adapters.console.commands.meld.presentation import (
    _meld_picker_entry,
    _meld_wait_context_view,
    _meld_wait_fragments,
    _meld_wait_view,
    _session_command,
    _session_route,
    _session_scope,
    _single_line,
    render_meld_incomplete_receipt,
    render_meld_receipt,
    render_meld_session,
)
from memcommit.adapters.console.commands.meld.workflow.workflow import (
    _accept,
    _assert_non_target_source_bindings,
    _assert_source_bindings,
    _assert_unapplied_target,
    _assess_and_save,
    _bound_frame_digest,
    _complete_default_terminal_execution,
    _interactive_terminal,
    _issue_selector,
    _load_bound_contexts,
    _load_local_meld_source,
    _load_meld_source,
    _meld_request_matches_saved_session,
    _preserve_all_guidance,
    _resolve_meld_source,
    _resume_picked_meld,
    _run_interactive,
    execute_meld_command,
    run_meld_review,
)
from memcommit.adapters.console.commands.meld.entrypoint import (
    _browse_saved_meld_sessions,
    _start_new_meld_from_setup,
    cmd,
)
from memcommit.adapters.console.commands.meld.entrypoint import (
    MemoryStore,
    choose_meld_setup,
    choose_session,
)
from memcommit.adapters.console.commands.meld.workflow.workflow import (
    connect_codex_chatgpt_provider,
    run_command_wait,
    run_meld_shell,
    sys,
)

__all__ = [
    "MeldCommandError",
    "_session_command",
    "_session_route",
    "_session_scope",
    "_single_line",
    "render_meld_session",
    "render_meld_receipt",
    "render_meld_incomplete_receipt",
    "_meld_wait_view",
    "_meld_wait_context_view",
    "_meld_wait_fragments",
    "_meld_picker_entry",
    "_interactive_terminal",
    "_preserve_all_guidance",
    "_issue_selector",
    "_load_bound_contexts",
    "_resolve_meld_source",
    "_is_inline_memory_operand",
    "_load_meld_source",
    "_load_local_meld_source",
    "_meld_request_matches_saved_session",
    "_bound_frame_digest",
    "_assert_source_bindings",
    "_assert_non_target_source_bindings",
    "_assert_unapplied_target",
    "_assess_and_save",
    "_accept",
    "_complete_default_terminal_execution",
    "_run_interactive",
    "run_meld_review",
    "_resume_picked_meld",
    "InterpretedMeldCommand",
    "MeldCommandInterpretationError",
    "MeldCommandRequest",
    "MeldSessionsCommand",
    "MeldSetupCommand",
    "interpret_meld_command",
    "execute_meld_command",
    "_browse_saved_meld_sessions",
    "_start_new_meld_from_setup",
    "cmd",
    "MemoryStore",
    "choose_meld_setup",
    "choose_session",
    "connect_codex_chatgpt_provider",
    "run_command_wait",
    "run_meld_shell",
    "sys",
]


class _CompatibilityFacade(_ModuleType):
    """Keep assignments to historical command seams visible to their owners."""

    def __setattr__(self, name, value):
        # The former single module was also a common test/integration injection
        # seam. Forward replacement values without making internal modules
        # depend back on this compatibility facade.
        for module in (_presentation, _workflow, _interpretation, _entrypoint):
            if name in module.__dict__:
                setattr(module, name, value)
        super().__setattr__(name, value)


_sys.modules[__name__].__class__ = _CompatibilityFacade
