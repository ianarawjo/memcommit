# Isolated memcommit study stores

Each `task-N/` directory is a complete, independent package whose `.mem/`
directory can be installed as one study run's local store. English is the
canonical Memory content. Korean is attached to the same Memory UID as an
unreviewed imported translation view. Query-only sources contain concealed
English and Korean variants and remain accessible only through `mem query`.

Do not merge these `.mem/` directories. Preserve the person's current
`~/.mem` under a separate backup name before installing exactly one package,
and restore that backup after the run. The package manifest records fixture
identity, runtime UID, source hashes, purpose, audience annotations, and the
translation review boundary; audience annotations are not ACL enforcement.
