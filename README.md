# MemCommit

MemCommit is a command-line memory store with named Contexts, editable Memories,
checkpoints, and semantic operations. Its console interface includes both
scriptable commands and interactive terminal workbenches.

This demo snapshot is published on the `innovathon` branch. It shares executable
code with the `user-study-prototype` snapshot and adds demo documents and examples.

## Install

Python 3.10 or later is required. With [uv](https://docs.astral.sh/uv/) installed,
run these commands from the repository root:

```sh
git switch innovathon
uv sync --locked
uv run --locked mem --help
```

The committed `uv.lock` records the resolved dependency versions. Alternatively,
install the package into a Python environment with `python -m pip install .`;
pip uses the dependency ranges in `pyproject.toml` rather than `uv.lock`.

## Try it

```sh
uv run --locked mem init demo
uv run --locked mem add "The cafe opens at nine."
uv run --locked mem list
uv run --locked mem checkpoint
uv run --locked mem log
```

These commands create local data in a workspace, defaulting to `~/memcommit`.
Internal configuration and Profile data live under `<workspace>/.mem/`;
`<workspace>/contexts/` is reserved for document work and does not automatically
import, export, or synchronize files.

To choose a workspace or migrate existing `~/.mem` / `~/.mem-profiles` data:

```sh
uv run --locked mem config set workspace_dir ~/memcommit
```

This copies and verifies existing data before selecting the new workspace; the
original files remain intact. Choose a new, unoccupied destination for relocation.
Only the workspace pointer lives outside the workspace, in
`~/Library/Application Support/memcommit/config.json` on macOS or
`~/.config/memcommit/config.json` elsewhere.
Use `mem --help` for the command list and `mem COMMAND --help` for exact options.
When using `uv`, prefix those commands with `uv run --locked`.

## Innovathon demo

Start with a new empty ordinary Profile:

```sh
uv run --locked mem profile create innovathon-demo
uv run --locked mem profile use innovathon-demo
```

Creation and selection are separate: `profile create` leaves the active
Profile unchanged; `profile use` selects the new empty store. No study fixture,
companion Profile, Context, or Memory is created by these two commands.

When ready, import the example documents explicitly from this checkout:

```sh
uv run --locked mem import skill --from examples/openai-docs -r --as openai-docs
```

The example files are input data, not instructions executed by the initializer.

## Study scenarios

The built-in Coffee Study includes its participant and granted-memory data:

```sh
uv run --locked mem init-study demo-study
uv run --locked mem profile list
uv run --locked mem contexts
```

`init-study` creates an isolated pair of Profiles and switches to the participant
Profile. An interactive terminal can also enter its Study shell. The older
fixture is available explicitly with `mem init-study NAME --scenario legacy`.
Both scenarios and their required data are included in the installed package.

## Semantic operations

Commands that call a language model require a configured provider. Supported
providers are Codex with a ChatGPT login, Ollama, and OpenRouter. Each requires
its own runtime or credentials; the Python package does not install those
services. Inspect the available settings and verify a connection with:

```sh
uv run --locked mem provider --help
uv run --locked mem provider use codex_chatgpt --reasoning low
uv run --locked mem provider status
uv run --locked mem provider probe
```

The example configures an ordinary Profile for Codex and requires an existing
ChatGPT login in the Codex CLI. Select a reasoning level supported by your model;
an unconfigured route can request `none`, which some models reject. Study
Profiles use their own fixed provider configuration.

## Update

Apply one instruction to the current Context or an explicit Target:

```sh
uv run --locked mem update "Set the cafe opening time to ten." --to demo
uv run --locked mem update -m instructions:MEMORY_UID --to demo
```

`-m` uses one stored Memory outside the Target as the instruction; it does not
select a Memory to edit. Update considers the Target's direct contents, without
expanding embedded or descendant Contexts. Submitting the command plans and
applies the changes, then prints their diff and completed receipt. Checkpoints,
Review, Undo and Redo retain the completed evidence.

The earlier Context-source syntax, endpoint setup screen, Apply confirmation,
and resumable Update sessions are removed. Repeating the command plans afresh.
`mem impact` remains a separate read-only preview operation.

## Merge and Resolve

`mem merge` opens an interactive setup for two existing Contexts. Semantic Merge
first handles structural conflicts, then reviews semantic issues in the merged
Context. `--literal` handles the stored items without language-model inference:

```sh
uv run --locked mem merge
uv run --locked mem merge incoming notes --literal
uv run --locked mem resolve --help
```

Merge and Resolve require an interactive terminal. Semantic checks can vary
between provider calls; this prototype does not guarantee identical findings on
repeated runs. Saved Audit records from earlier schema versions are not migrated
automatically by this snapshot.

## Developer scenarios

List the registered scenarios with `mem dev-eval`. Supplying a scenario name
runs its authored steps in the current Profile and prints their PASS/FAIL results:

```sh
uv run --locked mem dev-eval
uv run --locked mem dev-eval merge_visitor_notices
```

`merge_visitor_notices` currently exercises CLI Init and Add for two Contexts,
each with five visitor notices, and verifies the stored results. It prepares the
Merge inputs; it does not yet run the interactive Merge decisions.
`duplicates_coffee` exercises exact and semantic duplicate discovery and removal,
and requires a semantic provider. Both scenarios retain their created Contexts.

The Agent and Python API adapters remain reserved; the supported interface is
the Console CLI/TUI.

## Source layout

All executable package code and bundled resources live under `src/memcommit/`:

```text
core/             Core memory concepts and invariants
application/      Operations, capabilities, and authorization
adapters/console/ CLI commands and terminal components
providers/        Language-model provider integrations
persistence/      Stores, checkpoints, and saved sessions
configuration/    Global configuration
study_scenarios/  Built-in scenarios and their data
```
