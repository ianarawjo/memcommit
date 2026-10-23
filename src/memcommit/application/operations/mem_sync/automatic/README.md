# Deferred automatic Sync

The study uses explicit `mem sync`. The former `--always`, operation-start/end
checks, completion hooks, and Profile setup toggle have no executable path.
Old enabled settings do not authorize automatic synchronization.

TODO: reconsider automatic Sync for longer-term use after the manual conflict
policy and checkpoint agreement contract are stable. Restore from Git history
when needed; do not leave inactive wrappers around every command.
