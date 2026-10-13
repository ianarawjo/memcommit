# MemCommit

MemCommit is a command-line memory store with named Contexts, editable Memories,
checkpoints, and semantic operations. Its console interface includes both
scriptable commands and interactive terminal workbenches.

This prototype snapshot is published on the `user-study-prototype` branch.

## Install

Python 3.10 or later and Git are required. The current runtime is verified on
macOS. Native Windows execution is not yet supported: Store locking depends on
Unix `fcntl`, and isolated Study shells require zsh. A Windows Python install
alone does not make this snapshot compatible.

On macOS, check Git with `git --version`. If it is missing, run
`xcode-select --install` and complete the Command Line Tools installation.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal and verify `uv --version`. Then install the public prototype
and add uv's tool executable directory to your shell's PATH:

```sh
uv tool install --python 3.10 'git+https://github.com/ianarawjo/memcommit.git@user-study-prototype'
uv tool update-shell
```

Open another new terminal before running `command -v mem` and `mem --help`.
`uv tool update-shell` updates shell configuration; an already open terminal
may still have its previous PATH. See uv's
[tool executable documentation](https://docs.astral.sh/uv/concepts/tools/#tool-executables).

To use the installed tool immediately in the current macOS terminal:

```sh
export PATH="$(uv tool dir --bin):$PATH"
mem --help
```

To update a previously installed prototype, run `uv tool upgrade memcommit`.
The source installation below also provides `uv run --locked mem` without
requiring the `mem` executable itself on PATH.

### Windows: WSL2 setup route

Use a Linux environment in WSL2 for this Unix-based snapshot. Native PowerShell
or Command Prompt execution is not supported yet. This route is documented
from the platform instructions; it has not yet been verified on a Windows/WSL
machine.

If WSL is not installed, follow Microsoft's
[WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).
In an administrator PowerShell, run:

```powershell
wsl --install -d Ubuntu
```

Restart Windows if prompted, launch Ubuntu, and finish its user setup. In the
**Ubuntu terminal**, install the required Linux tools and uv:

```sh
sudo apt update
sudo apt install -y git curl zsh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new Ubuntu terminal and check `git --version`, `zsh --version`, and
`uv --version`. Install memcommit inside Ubuntu:

```sh
uv tool install --python 3.10 'git+https://github.com/ianarawjo/memcommit.git@user-study-prototype'
uv tool update-shell
export PATH="$(uv tool dir --bin):$PATH"
mem --help
```

The Windows and WSL installations have separate executable paths and home
directories. Install semantic-provider tools and sign in inside the same WSL
environment that runs memcommit.

For the initial setup, keep projects in the Linux filesystem, for example
`~/projects/my-project`, and pass Linux paths to `--root`. See Microsoft's
[filesystem guidance](https://learn.microsoft.com/en-us/windows/wsl/filesystems).
Windows-mounted folders such as `/mnt/c/...` have different permission
semantics and are outside this initial setup route; see
[WSL file permissions](https://learn.microsoft.com/en-us/windows/wsl/file-permissions).

### Source installation

For a source checkout with locked dependencies:

```sh
git clone --branch user-study-prototype --single-branch https://github.com/ianarawjo/memcommit.git
cd memcommit
uv sync --locked
uv run --locked mem --help
```

The committed `uv.lock` records resolved dependency versions. Alternatively,
install from a checkout with `python -m pip install .`. The examples below use
`mem` from a tool installation; in a source checkout, use `uv run --locked mem`.

## Try it

```sh
mem init demo
mem add "The cafe opens at nine."
mem list
mem checkpoint
mem log
```

## Project folders and document Sync

The default `authoring` Profile stores its data and history in
`~/.memcommit/authoring/.mem/`. Connect another Profile to your project folder:

```sh
mem profile create my-project --root /path/to/my-project
mem profile use my-project
mem profile config
```

Each registered project has its own `.mem/` for internal data, checkpoints,
settings, and saved operation history. Commands use the selected Profile.
Creating a Profile leaves existing project files unchanged and does not select
it automatically. A second Profile at the same or an overlapping folder is
rejected. When `--root` is omitted, a new Profile gets a separate directory under
`~/.memcommit/projects/`. The interactive `mem profile` creation screen lets you
choose a folder, initially suggesting the current directory.

From the registered project folder, import supported existing documents and
synchronize them back to those paths:

```sh
cd /path/to/my-project
mem import .
mem sync -a
mem sync -a --always
```

Import retains paths such as `AGENTS.md`, `.agents/skills/reviewer/SKILL.md`, and
`.claude/rules/project.md`. Ordinary document import supports Markdown, text,
YAML, and YML; `.mdc` is not yet supported. `.mem` and `.git` are excluded.
An initial Sync adopts identical files, creates missing files, and reports a
conflict when existing bytes differ. Unmanaged project files are preserved.

`--always` toggles automatic outbound Sync for the selected scope. Once enabled,
successful mem commands synchronize changed Memories to the project files;
Undo and Redo can synchronize their resulting content too. Repeating
`mem sync -a --always` disables it. External edits are detected as conflicts;
there is no background or automatic inbound file watcher.

For an independent copy, use Export:

```sh
mem export AGENTS.md --to /path/to/export-copy
```

The registered project folder is the Sync destination. To relocate an existing
Profile with its Store and connected documents, use:

```sh
mem profile config set root_dir /new/project-folder
```

This verifies the copy and selects the new folder while retaining the original
files. Global settings live in `~/.memcommit/config.json`, separately from each
project's `.mem`. This prototype starts with the current location and registry
schema; it does not automatically migrate older workspace or registry data.

Use `mem --help` for the command list and `mem COMMAND --help` for exact options.

## Study scenarios

The built-in Coffee Study includes its participant and granted-memory data:

```sh
mem init-study demo-study
mem profile list
mem contexts
```

`init-study` creates an isolated pair of Profiles and switches to the participant
Profile. An interactive terminal can also enter its Study shell. The older
fixture is available explicitly with `mem init-study NAME --scenario legacy`.
Both scenarios and their required data are included in the installed package.
New runs default to `~/.memcommit/studies/<Study UID>/participant/` and
`authority/`, each with its own `.mem/`. The participant shell starts in its
registered project folder. To choose the parent for future runs:

```sh
mem config set study_root_dir /path/to/studies
```

## Semantic operations

Commands that call a language model require a configured provider. Supported
providers are Codex with a ChatGPT login, Ollama, and OpenRouter. Each requires
its own runtime or credentials; the Python package does not install those
services. Inspect the available settings and verify a connection with:

```sh
mem provider --help
mem provider use codex_chatgpt --reasoning low
mem provider status
mem provider probe
```

The example configures an ordinary Profile for Codex and requires an existing
ChatGPT login in the Codex CLI. Select a reasoning level supported by your model;
an unconfigured route can request `none`, which some models reject. Study
Profiles use their own fixed provider configuration.

## Update

Apply one instruction to the current Context or an explicit Target:

```sh
mem update "Set the cafe opening time to ten." --to demo
mem update -m instructions:MEMORY_UID --to demo
```

`-m` uses one stored Memory outside the Target as the instruction; it does not
select a Memory to edit. Update considers the Target's direct contents, without
expanding embedded or descendant Contexts by default. Use `--recursive` to
update the Target, lexical descendants, and embedded Contexts together.
Submitting the command plans and applies the changes, then prints their diff
and completed receipt. Checkpoints,
Review, Undo and Redo retain the completed evidence.

The earlier Context-source syntax, endpoint setup screen, Apply confirmation,
and resumable Update sessions are removed. Repeating the command plans afresh.
`mem impact` remains a separate read-only preview operation.

## Merge and Resolve

`mem merge` opens an interactive setup for two existing Contexts. Semantic Merge
first handles structural conflicts, then reviews semantic issues in the merged
Context. `--literal` handles the stored items without language-model inference:

```sh
mem merge
mem merge incoming notes --literal
mem resolve --help
```

Merge and Resolve require an interactive terminal. Semantic checks can vary
between provider calls; this prototype does not guarantee identical findings on
repeated runs. Saved Audit records from earlier schema versions are not migrated
automatically by this snapshot.

## Developer scenarios

List the registered scenarios with `mem dev-eval`. Supplying a scenario name
runs its authored steps in the current Profile and prints their PASS/FAIL results:

```sh
mem dev-eval
mem dev-eval merge_visitor_notices
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
