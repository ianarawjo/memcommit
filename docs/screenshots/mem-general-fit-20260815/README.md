# General Fit TTY evidence — 2026-08-15

This ordered record exercises the public role-neutral Fit command at
`180 x 52` in a true-color PTY. `NO_COLOR` is removed and
`TERM=xterm-256color`, `COLORTERM=truecolor`, and prompt-toolkit 24-bit color
are explicit. The provider is deterministic so the screenshots characterize
the interface and contract rather than an unstable live semantic sample.

The exact command represented in every state is:

```text
mem fit "The main entrance is closed after 5 p.m." "Staff may use the entrance after 6 p.m." --background "The building has separate main and staff entrances."
```

The process uses no Profile or current Context. The background and two
propositions are process-local, and every step has `DURABLE WRITES · 0`.

| # | File | Preceding input | Visible state | Durable effect |
| --- | --- | --- | --- | --- |
| 01 | `01-provider-running` | command entry | bounded provider progress before a result exists | none |
| 02 | `02-judgment-entry` | provider returns | `? MAY`, reason, and Judgment focus | none |
| 03 | `03-complete-input-focused` | `Down` | complete frozen background and both propositions | none |
| 04 | `04-readings-focused` | `Down` | one ordinary consistent and one inconsistent reading | none |
| 05 | `05-focused-copy` | `y` | focused Readings section copied | clipboard only |
| 06 | `06-complete-copy` | `Y` | complete Judgment + inputs + readings copied | clipboard only |
| 07 | `07-read-only-verification` | `q` | Viewer closed; verdict, two copies, and zero durable writes verified | none |

The semantic label boundary was separately exercised against the configured
live provider with the controlled entrance contrast:

- explicit different entrances returned `YES`;
- same main entrance with overlapping prohibition and permission returned
  `NO`; and
- unresolved `the entrance` returned `MAY` with both readings exposed.
