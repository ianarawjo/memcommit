# Portable Context name and compatibility migration rationale

## Problem and intended behavior

The historical Context storage validator protected the local filesystem but
accepted names such as `team project`, `$draft`, `*`, or a leading `-`. Those
names are valid persisted locators once passed to the process as one argument,
but a person may need shell quoting, escaping, or an explicit `--` to pass them
unchanged. Quoting is shell syntax rather than part of the Context identity:
`team/project` and `"team/project"` already reach `mem` as the same argument,
while `team project` cannot be entered unquoted as one argument.

New Context identities therefore use one portable spelling that behaves the
same with or without ordinary shell quotes. Existing broader names remain
readable and writable until the person runs an explicit compatibility
migration. This is a staged naming-policy change, not an eager store-format
break.

Canonical UUID values already contain only hexadecimal digits and hyphens, so
quoting a UID is optional and does not change the value received by the CLI.
That quote-independent spelling also means a root Context named like a UUID or
one of the eight-or-more-character UID prefixes displayed by the CLI would be
ambiguous in an automatically typed operand. New Context identities reserve
that complete-root spelling for Memory selectors.

## Portable name contract

A portable Context name is a slash-delimited sequence of segments. Every
segment must:

- start with an ASCII letter or digit;
- continue with only ASCII letters, digits, `.`, `_`, or `-`;
- not end with `.`;
- not equal a storage-reserved segment such as `context.json` or
  `checkpoints`, case-insensitively; and
- not use a Windows device basename such as `CON`, `NUL`, `COM1`, or `LPT1`,
  including an extension such as `nul.txt`.

Slash is the only namespace separator. Empty segments, leading or trailing
slashes, whitespace, Unicode letters, shell expansion characters, control
characters, and a leading `-`, `.`, or `_` segment character are rejected for
new identities. Representative accepted names are `team`, `team/project`,
`Team_29/project-v2`, and `release.2026`. A complete name must additionally not
match the public Memory UID-selector shape: at least the first eight
hexadecimal characters of a canonical hyphenated UUID. Thus `deadbeef` is not
a new Context name, while `team/deadbeef` remains unambiguous and valid because
the slash types the complete operand as a Context locator. If `--parents`
would create `deadbeef` as its own parent Context, validation rejects the
complete batch before publication.

The contract deliberately uses an ASCII subset. Broader Unicode names could
be made safe with normalization and shell-aware display, but would still vary
across filesystems, shells, fonts, and copy/paste boundaries. A portable
durable locator is more valuable here than maximizing the display-name
alphabet; descriptive prose remains Unicode-capable.

## Enforcement boundary

`memcommit.context_naming.validate_portable_context_name` is the shared
new-identity validator. The Store enforces it whenever a record does not
already exist, so a missed command-local check cannot publish a new legacy
name. Creation and destination adapters also validate early so interactive
screens and semantic operations fail before provider work or approval.

The portable rule applies to:

- `init`, branch destinations, Ground workspace Save Locations, and missing
  Context batches;
- Find, Distill, explicit Sever OTHER-SAVE, Meld new-Result, and other
  require-new result destinations;
- ordinary Context and Memory import destinations;
- new query-only source identifiers; and
- new Grant resource, attachment, public, and recursively frozen binding
  names.

A whole-Profile archival import may still contain legacy records because its
purpose is to preserve an existing store exactly. Ordinary imports that
publish new identities use the portable rule.

## Compatibility boundary

The historical `validate_context_name` remains the read-time storage contract.
Consequently an existing legacy Context can still be listed, loaded, selected,
updated, checkpointed, reverted, and used by existing-Context operations. The
Store only invokes the portable validator on `save` when the target Context
does not already exist. `mem contexts` labels local legacy rows
`LEGACY NAME · MIGRATION REQUIRED` so compatibility does not make the debt
invisible.

Existing Grants are also decoded under their historical locator contract.
Their existing readable view remains usable while all frozen UID/name
bindings agree; a downstream operation that must create another Context below
a legacy attachment still fails the new-identity rule. A new Grant may not
publish or attach a legacy locator, and an explicit recursive scope refresh
may not add one. A visible granted legacy name is labelled
`LEGACY GRANT NAME · RECREATE REQUIRED`.

This asymmetry is intentional: rejecting legacy reads would strand data, while
allowing new writes would make the migration boundary permanent and
unmeasurable.

The same compatibility boundary applies to an existing UUID-shaped root
Context. It remains listable and readable and can be selected through an
explicit Context operand such as `--context`; automatic Fit operands reserve
that spelling for Memory lookup. Migration to a descriptive non-UID name is
the route to automatic positional selection.

## Compatibility migration command

The public migration route is:

```text
mem profile migrate-context -- LEGACY_CONTEXT PORTABLE_CONTEXT
mem profile migrate-context --expect-profile PROFILE_UUID \
  --expect-graph SHA256 --apply -- LEGACY_CONTEXT PORTABLE_CONTEXT
```

The first form is read-only. It prints the frozen source/destination mapping,
affected Context and reference counts, derived-binding counts, any remaining
nonportable descendants, Grant blockers, and one shell-escaped apply command.
The `--` in that receipt also lets a legacy leading-dash source be passed
unambiguously. `--apply` is accepted only with the Profile UID and Context
graph digest printed by that preview. A Profile switch or graph change makes
the receipt stale before mutation. The accepted receipt executes the same
Store graph migration and retains the existing collision, UID, reference,
checkpoint, Ground, translation, Meld, rollback, and write-protection checks
documented in `mem-rename-design-rationale.md`.

The Apply line is executable in zsh and bash. A legacy name containing a bidi
or other display-control code point is rendered with ANSI-C Unicode escapes,
so the terminal never receives the raw control while the shell still
reconstructs the exact stored locator.

The command accepts only a nonportable source and a portable destination. It
is therefore a compatibility route, not a second general Context rename UI.
A subtree move can leave a nonportable descendant segment—for example,
`old root/bad child` to `old-root/bad child`. The receipt reports the remaining
canonical names and the person migrates those roots in later reviewed steps.

## Grant and query-only migration boundaries

Cross-Profile Grants freeze owner and attachment locator names alongside UIDs.
Silently rewriting them from one Profile's Context migration would cross an
authority boundary and could change a grantee's public namespace without that
party reviewing it. Migration therefore fails before mutation when an active
Grant refers to the source subtree as an authority resource, frozen binding,
or grantee attachment. The person must delete the listed Grant, migrate the
ordinary Context, and recreate the Grant with portable names.

Legacy query-only sources are not opened or rewritten by ordinary Context
migration. Their provider and retention contracts differ from ordinary local
records, and a `QueryContextRef` is deliberately left unchanged by the graph
migration. A legacy query-only installation must be replaced through its
owning import or study setup route rather than being silently converted.

## Alternatives considered

- **Require quotes for broad names:** rejected because quoting belongs to the
  invoking shell, varies by environment, and does not solve leading-option or
  cross-filesystem ambiguity.
- **Strip quotes inside `mem`:** rejected because a real quote character may
  be data and normal shells remove syntactic quotes before starting `mem`.
- **Let an existing UUID-shaped Context outrank a Memory selector:** rejected
  because the meaning of a bare UID would then depend on unrelated namespace
  occupancy. Explicit legacy Context selection preserves access without
  weakening the new unambiguous operand grammar.
- **Reject all legacy names immediately:** rejected because it would make
  existing stores, checkpoints, references, and Grants inaccessible before a
  safe migration could run.
- **Silently normalize on load or save:** rejected because names are durable
  locators. Changing one record without migrating the complete UID-bound graph
  would create stale pointers and collisions.
- **Automatically rewrite Grants and query sources:** rejected because those
  records cross authority or provider boundaries and require their own review.

## Remaining limitations

The migration inherits the graph relocation primitive's exception atomicity
and lack of a durable crash journal. It does not create aliases, redirect old
names, merge an occupied destination, or rename query-only sources. External
scripts that persist a legacy literal must be updated after migration. The
portable contract prevents ordinary shell quoting from being required; it
does not remove the general rule that arbitrary user-supplied values should be
passed as argument-array entries rather than interpolated into shell source.
