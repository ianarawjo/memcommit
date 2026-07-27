# Repository agent instructions

## Running `mem` commands

- When the user enters a `mem` command, such as `mem ls`, run the command from
  this repository's root and report its actual output instead of only
  describing what it would do.
- Use the repository root as the default working directory; `cd` or `pwd` is
  only needed when the user explicitly requests it or the working directory
  must be diagnosed.
- If the `mem` executable is not available on `PATH`, run the equivalent
  project entry point with `python -m memcommit.cli ...` and clearly identify
  that fallback.
