# MemCommit

MemCommit is a command-line memory store with named Contexts, editable Memories,
checkpoints, and semantic operations. Its console interface includes both
scriptable commands and interactive terminal workbenches.

## Install

Python 3.10 or later is required. With [uv](https://docs.astral.sh/uv/) installed,
run these commands from the repository root:

```sh
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

These commands create local data. MemCommit stores configuration and Profile
metadata under `~/.mem`, and additional Profile stores under `~/.mem-profiles`.
Use `mem --help` for the command list and `mem COMMAND --help` for exact options.
When using `uv`, prefix those commands with `uv run --locked`.

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

`mem eval` currently reserves a name for a future evaluation workflow; it does
not yet implement evaluation commands. The Agent and Python API adapters are
also reserved; the supported interface is the Console CLI/TUI.

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
