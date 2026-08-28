# Agent adapters

Agent-facing adapters expose reviewed MemCommit application use cases as
strict, host-neutral JSON tool contracts. The frozen in-process registry is
the composition boundary for machine callers; protocol transports are not
owned or shipped by this package. The package root is intentionally a marker;
callers import operation contracts or `registry` from their owning modules so
an unrelated adapter is not assembled eagerly.
