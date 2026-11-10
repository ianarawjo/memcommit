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
PATH, and opens `mem`. Initial setup starts automatically when no registered
Profile or legacy authoring Store exists.
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
retain their selected Profile; later settings use `mem llm-provider`, `mem config`,
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

Run Sync to discover and synchronize supported project documents:

```sh
mem sync
```

Markdown paths such as `AGENTS.md`, `.agents/skills/reviewer/SKILL.md`, and
`.claude/rules/project.md` retain their corresponding Context names. Internal
`.mem` and `.git` data are excluded. Sync compares both sides against checkpoint
history. When only one side changed, that version is used. When both sides
changed differently, choose the external or mem version once for every conflict
in the Profile. Both versions remain in checkpoint history, and Undo/Redo
restores the entire Sync action at once.

Automatic Sync is optional and starts off for ordinary Profiles:

```sh
mem sync --auto on
mem sync --auto status
mem sync --auto off
```

When enabled, a background worker observes Markdown edits and mem actions.
Conflicts still require an explicit `mem sync` decision. A failed command pauses
automatic publication until the next explicit mem action. The worker survives
terminal closure; after reboot or worker exit, a mem command restarts it while
the Profile's automatic setting remains enabled.

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

## Study project placeholders

The public source and installed package retain three empty folders under
`application/operations/init_study/study_scenarios/`: `isaac`, `peter`, and
`practice`. Each contains only `.gitkeep`. Study documents, prepared `.mem`
Stores, and Sync checkpoints remain in the private research repository.

`mem init-study` remains in the executable code but requires valid prepared
projects, which this public distribution does not include. Use ordinary
Profiles for the public examples above. Contexts directly contain Memories;
Embed, Reference, Share, and Grant execution remain reserved in this snapshot.

## Semantic operations

Commands that call a language model require a configured provider. Initial
setup offers Codex with a ChatGPT login and verifies a synthetic response before
creating the first Profile. Credentials remain with the provider; installing
MemCommit does not transfer a login to another computer.

Inspect or change shared provider settings with:

```sh
mem llm-provider status
mem llm-provider configure
mem llm-provider probe
```

The configuration screen selects a Codex model and supported reasoning effort.
Settings are shared across Profiles. Init, Add, List, and document Sync can be
used without making language-model calls. See `mem llm-provider --help` for the
available commands.

## Update

Apply one instruction to the current Context:

```sh
mem switch demo
mem update "Set the cafe opening time to ten."
```

Update considers the current Context's direct contents. Use `-r` or `--recursive`
to update the current Context and its lexical descendants together.
Submitting the command plans and applies the changes, then prints their diff
and completed receipt. Checkpoints, Undo and Redo retain the completed evidence.

The earlier Context-source syntax, endpoint setup screen, Apply confirmation,
and resumable Update sessions are removed. Repeating the command plans afresh.
Direct Update has no dedicated Impact or Review route. `mem impact` remains a
read-only preview for the operations listed in its Help.

## Merge and Conflict

`mem merge` opens an interactive setup for two existing Contexts. Semantic Merge
handles structural conflicts and reviews semantic issues in the merged Context.
`--literal` combines stored items without language-model inference:

```sh
mem merge
mem merge incoming notes --literal
mem conflict --help
```

Interactive review requires a terminal. Semantic checks can vary between
provider calls; this prototype does not guarantee identical findings on repeated
runs. Saved records from older prototype schemas are not migrated automatically.

## Developer checks

`mem dev-eval` lists the available developer scenarios. Supplying a scenario name
runs its authored steps in the current Profile and prints PASS/FAIL results.
These checks can create Contexts; semantic scenarios require a provider.
The supported application interface is the Console CLI/TUI.

## Source layout

All executable package code and bundled resources live under `src/memcommit/`:

```text
models/           Memory, Context, Checkpoint, Profile, and metadata models
core/             Remaining shared memory concepts and pure helpers
application/      Operations, capabilities, and authorization
adapters/console/ CLI commands and terminal components
llm_providers/    Language-model provider integrations
persistence/      Stores, checkpoints, and saved sessions
configuration/    Global configuration
application/operations/init_study/study_scenarios/
                  Three empty Study project placeholders
```


## Setup for an AI agent

Open `mem` in a terminal after installation so the person can complete
Codex's ChatGPT login and initial Provider/model/Profile choices. Plain
`uv tool install` installs the package; opening mem starts the initial setup
flow. The installer opens it automatically when a terminal is available and
otherwise prints that next step. Interrupted setup resumes by opening mem.

Import starts ON and can be changed on the Profile creation screen before exact
approval. Document synchronization uses `mem sync`, with optional `--auto on`. Authentication
stays with Codex; do not collect or write the person's tokens. The active Profile
remains selected until changed with `mem profile use NAME`. Existing registered
Profiles are kept.

First setup writes Profile registry version 8. This snapshot does not migrate
older registry or Context storage formats.
