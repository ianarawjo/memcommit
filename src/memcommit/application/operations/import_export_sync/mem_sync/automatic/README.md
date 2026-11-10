# Optional automatic Sync

`mem sync --auto on|off|status` controls fresh, default-off consent for the active
Profile. Obsolete automatic settings and retired flags do not authorize it.
This package owns automatic execution policy and reuses ordinary Sync planning
and publication; adapters own detached polling and command-boundary scheduling.

The watcher observes supported `.md` documents, `.memignore`, and native Contexts,
waits for stable inputs, and shares an operation lease with explicit Sync and
enabled CLI commands. Unchanged polls create no receipts. Conflicts never choose
a side automatically: use ordinary `mem sync` to resolve them. A failed CLI
command pauses automatic publication until the next explicit mem action.

Consent is durable; the detached process survives terminal closure but is not an
OS login service. After reboot or worker exit, an ordinary mem command or
`mem sync --auto on` restarts it. Profile root, Store identity, and Profile ownership
remain frozen; switching the active Profile does not retarget a worker.
