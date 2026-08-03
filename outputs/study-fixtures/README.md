# Isolated memcommit study stores

Each `task-N/` directory is a complete, independent package whose `.mem/`
directory can be copied into one editable local profile. English is the
canonical Memory content. Korean is attached to the same Memory UID as an
unreviewed imported translation view. Query-only sources contain concealed
English and Korean variants and remain accessible only through `mem query`.

Do not merge these `.mem/` directories. Run `mem profile import-study` to
register editable copies, then use `mem profile use task-N` before navigating
that task with `mem switch`. The legacy `~/.mem` remains the `authoring`
profile and package sources are never edited in place. The package manifest
records fixture identity, runtime UID, source hashes, purpose, and the
translation review boundary; audience annotations are not ACL enforcement.
