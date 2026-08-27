# MemCommit

src/memcommit/
  core/             # Core concepts and invariants for Memory, Context, and history
  application/      # Operation-specific use cases, execution flows, and port contracts
  adapters/         # Input/output adapters for Console, Python API, and Agent interfaces
    console/        # Shared terminal adapter for CLI and TUI interactions
  commands/         # Current CLI and TUI command entry points
  providers/        # External semantic and LLM provider implementations
  persistence/      # Persistent storage for Stores, checkpoints, snapshots, and sessions
  configuration/    # Configuration models, loading, and validation for files and environment variables
  study_scenarios/  # Study scenarios used by init-study
  bootstrap.py      # Composition root that assembles implementations and wires dependencies to entry points