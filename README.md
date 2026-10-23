# MemCommit

MemCommit is a command-line memory store with named Contexts, editable Memories,
checkpoints, and semantic operations. Its console interface includes both
scriptable commands and interactive terminal workbenches.

This prototype snapshot is published on the `user-study-prototype` branch.

## Install on macOS

Run this command from the folder you want to use as your first workspace:

```sh
curl -fsSL https://raw.githubusercontent.com/ianarawjo/memcommit/user-study-prototype/src/memcommit/installation/install.sh | sh
```

The installer finds or prepares [uv](https://docs.astral.sh/uv/getting-started/installation/),
installs memcommit in a tool environment with Python 3.12, registers `mem` on
PATH, and opens `mem`. Initial setup starts automatically when provider settings
are incomplete or no registered Profile or legacy authoring Store exists.
Open a new terminal after installation if your
current shell has not picked up the PATH change. The bootstrap installs the
public source archive without requiring Git.

The current setup offers **OpenAI Codex only**. It finds or offers to install
the official Codex CLI, lets you complete ChatGPT login, and checks an actual
synthetic response before creating the first Profile. After login, it reads
Codex's model catalog: choose a model in the vertical list, then Tab to the
horizontal reasoning choices and use Left/Right. Codex supplies recommended
models, supported efforts and defaults. Compatible explicit efforts survive
model changes; unavailable efforts return visibly to the new model's default.
Enter checks the exact model and effort before saving them. Claude Code and
GitHub Copilot are planned additions.

A **Profile is a folder workspace**. Import of existing supported documents is
enabled initially and includes this folder's subfolders. Run `mem sync` explicitly
to synchronize the Profile's documents and Memories.
Review the folder, document count, options and exact creation command. Creating
the first Profile also selects it. If setup starts from your home directory,
its editable folder suggestion is `~/mem`.

For another workspace, enter its folder and run `mem profile`, then choose New
Profile. Select it with `mem profile use NAME`. Changing directory alone does
not switch the selected Profile. `mem init NAME` creates a Context inside it.
Open `mem` again to resume interrupted initial setup. Existing installations
retain their selected Profile; later settings use `mem provider`, `mem config`,
and `mem profile`.

If uv is already available, you can install explicitly:

```sh
uv tool install --upgrade --python 3.12 'git+https://github.com/ianarawjo/memcommit.git@user-study-prototype'
uv tool update-shell
export PATH="$(uv tool dir --bin):$PATH"
mem
```

This Git source route requires Git (`xcode-select --install` can prepare it on
macOS). `uv tool upgrade memcommit` updates an installed prototype.

Native Windows execution is not yet supported: Store locking depends on Unix
`fcntl`, and isolated Study shells require zsh. The automatic installer is
macOS-only. The Windows/WSL route below remains unverified on a Windows machine.

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

To import supported documents during creation, use:

```sh
mem profile create my-project --root /path/to/my-project --import-files
mem profile use my-project
```

Import includes supported nested and hidden document paths. Creation preserves
existing document bytes and keeps the previous Profile selected. The interactive
`mem profile` creation screen exposes the same Import option.

From the registered project folder, import supported existing documents and
synchronize them back to those paths:

```sh
cd /path/to/my-project
mem import .
mem sync
```

Import retains paths such as `AGENTS.md`, `.agents/skills/reviewer/SKILL.md`, and
`.claude/rules/project.md`. Ordinary document import supports Markdown, text,
YAML, and YML; `.mdc` is not yet supported. `.mem` and `.git` are excluded.
With no Context argument, Sync discovers and synchronizes the selected Profile's
project documents. It compares both sides against checkpoint history. When only
one side changed, that version is used. When both sides changed differently,
choose the external or mem version once for every conflict in the Profile.
Both versions remain in checkpoint history, and Undo/Redo restores the entire
Sync action at once. Sync is explicit; automatic Sync and `--always` are reserved
for future work.

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

The built-in Coffee Study includes its task Contexts and Memories:

```sh
mem init-study demo-study
mem profile list
mem contexts
```

`init-study` creates one isolated Study Profile containing the task Contexts and
switches to it. An interactive terminal can also enter its Study shell. The older
fixture is available explicitly with `mem init-study NAME --scenario legacy`.
Both scenarios and their required data are included in the installed package.
New runs default to `~/.memcommit/studies/<Study UID>/participant/`, with their
own `.mem/`. The participant shell starts in its registered project folder.
To choose the parent for future runs:

```sh
mem config set study_root_dir /path/to/studies
```

Study `mem help` shows these 20 commands to reduce the number of commands a
participant needs to learn:

```text
add       audit     branch    contexts  delete
edit      find      help      init      list
merge     profile   pwd       query     redo
resolve   switch    sync      undo      update
```

This list controls Study Help visibility. Contexts directly contain Memories;
Embed, Reference, Share, and Grant execution are reserved for future work in
this snapshot.

## Semantic operations

Commands that call a language model require a configured provider. Supported
providers are Codex with a ChatGPT login, Ollama, and OpenRouter. Each requires
its own runtime or credentials; the Python package does not install those
services. Init, Add, List, Import, Export, and document Sync can be used before
setting up a language-model provider.

### Codex: install, sign in, and connect

On macOS or inside WSL Ubuntu, install the Codex CLI using the
[official OpenAI installation instructions](https://learn.chatgpt.com/docs/codex/cli):

```sh
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

Open a new terminal so the installer's PATH change takes effect. Check the CLI,
then sign in with the ChatGPT account that will run semantic operations:

```sh
codex --version
codex login
codex login status
```

`codex login` opens the browser sign-in flow. If the browser cannot be opened
from WSL or a remote terminal, use `codex login --device-auth` and follow its
instructions. See the [official login command reference](https://learn.chatgpt.com/docs/developer-commands?surface=cli#codex-login).
For this prototype, the status must say `Logged in using ChatGPT`; an API-key
login is not accepted by the `codex_chatgpt` route.

For an ordinary Profile, select the provider and verify an actual connection:

```sh
mem provider use codex_chatgpt --reasoning low
mem provider status
mem provider probe
```

Select a reasoning level supported by your model; an unconfigured route can
request `none`, which some models reject. Study Profiles use their own fixed
provider configuration: install and sign in to the Codex CLI in the same
environment, then run `mem provider status` and `mem provider probe` in the
selected Study Profile without overriding its provider settings.

If `codex` cannot be found, reopen the terminal and check the CLI installer's
PATH instructions. If mem reports that authentication overrides are set, the
`codex_chatgpt` route requires a shell without `OPENAI_API_KEY`, `CODEX_API_KEY`,
or `CODEX_ACCESS_TOKEN` overrides. Provider login and settings must be prepared on
each new computer; installing memcommit does not transfer credentials.
Use `mem provider --help` for Ollama, OpenRouter, and the complete settings.

## Update

Apply one instruction to the current Context:

```sh
mem switch demo
mem update "Set the cafe opening time to ten."
```

Update considers the current Context's direct contents. Use `-r` or `--recursive`
to update the current Context and its lexical descendants together.
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
models/           Memory, Context, Checkpoint, Profile, and metadata models
core/             Remaining shared memory concepts and pure helpers
application/      Operations, capabilities, and authorization
adapters/console/ CLI commands and terminal components
providers/        Language-model provider integrations
persistence/      Stores, checkpoints, and saved sessions
configuration/    Global configuration
study_scenarios/  Built-in scenarios and their data
```


## Setup for an AI agent

Open `mem` in a terminal after installation so the person can complete
Codex's ChatGPT login and initial Provider/model/Profile choices. Plain
`uv tool install` installs the package; opening mem starts the initial setup
flow. The installer opens it automatically when a terminal is available and
otherwise prints that next step. Interrupted setup resumes by opening mem.

Import starts ON and can be changed on the Profile creation screen before exact
approval. Document synchronization uses explicit `mem sync`. Authentication
stays with Codex; do not collect or write the person's tokens. The active Profile
remains selected until changed with `mem profile use NAME`. Existing registered
Profiles are kept.

First setup writes Profile registry version 8. This snapshot does not migrate
older registry or Context storage formats.
