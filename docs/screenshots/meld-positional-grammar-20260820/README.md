# Meld positional grammar captures

These captures record the directional-first Meld grammar introduced on
2026-08-20:

```text
mem meld A       → A is INCOMING; current Context is BASELINE
mem meld A B     → A is INCOMING; B is BASELINE
mem meld A B C   → A and B are equal PEER sources; C is RESULT
```

The run used an isolated temporary MemoryStore, deterministic local provider
fixtures, and a real color-capable PTY sized and verified at 180 columns × 52
rows. `TERM=xterm-256color`, `COLORTERM=truecolor`, and prompt-toolkit 24-bit
color were enabled; `NO_COLOR` was removed. The retained `.typescript` streams
contain both true-color foreground (`38;2`) and background (`48;2`) ANSI.

The PNGs are faithful renders of those PTY byte streams through `pyte` and
Pillow rather than GUI terminal-window screenshots. Each capture also has a
plain final-canvas `.txt` projection. Run `python capture.py` from the
repository root to reproduce the set.

## Ordered interaction log

1. `01-help-positional-forms`
   - Command: `mem meld --help`
   - Current Context: `grammar/one/current-baseline`
   - Keys before capture: none
   - State: the three positional roles and explicit aliases are visible
   - Durable mutation: none

2. `02-one-operand-current-baseline`
   - Command: `mem meld grammar/one/incoming`
   - Current Context: `grammar/one/current-baseline`
   - Keys before capture: none after provider completion
   - State: `grammar/one/incoming` is visibly INCOMING and the frozen current
     Context is visibly `BASELINE / TARGET`; one required review item remains
   - Durable mutation: saves the directional Meld session; no Context Memory
     changes and no checkpoint

3. `03-one-operand-close-receipt`
   - Preceding key: `q`
   - State: stable non-applying session receipt with the explicit portable
     continuation `mem meld grammar/one/incoming
     grammar/one/current-baseline ...`
   - Durable mutation: none after the session created in step 2

4. `04-two-operand-directional`
   - Command: `mem meld grammar/two/incoming grammar/two/baseline`
   - Current Context: still `grammar/one/current-baseline`
   - Keys before capture: none after provider completion
   - State: both positional roles are visible as INCOMING and
     `BASELINE / TARGET`; the unrelated current Context is not an operand
   - Durable mutation: saves the second directional Meld session; no Context
     Memory changes and no checkpoint

5. `05-two-operand-close-receipt`
   - Preceding key: `q`
   - State: stable non-applying two-operand directional receipt
   - Durable mutation: none after the session created in step 4

6. `06-three-operand-symmetric`
   - Command: `mem meld grammar/three/peer-a grammar/three/peer-b
     grammar/three/result-c`
   - Current Context: still `grammar/one/current-baseline`
   - Keys before capture: none after Compare-basis completion
   - State: SOURCE A, SOURCE B, and RESULT C are all visible; neither peer is
     authoritative and one required symmetric conflict remains
   - Durable mutation: saves the ordered Compare basis, creates the empty
     `grammar/three/result-c`, and saves its symmetric Meld session atomically;
     no source or Result Memory changes and no application checkpoint

7. `07-three-operand-close-receipt`
   - Preceding key: `q`
   - State: non-applying receipt retains explicit `--to
     grammar/three/result-c` continuation commands
   - Durable mutation: none after step 6

8. `08-read-only-verification`
   - Commands: `mem status`, then `mem show --context
     grammar/three/result-c`, followed by process-local contract checks
   - Current Context: `grammar/one/current-baseline` (`UNCHANGED`)
   - Keys before capture: none
   - State: both directional targets own `AWAITING_REPLY` sessions and one
     Memory each; the symmetric Result owns an `AWAITING_REPLY` session and
     remains empty
   - Durable mutation: none

No Apply, defer, preserve, or semantic response key was sent during the path.
The final read-only check confirms that command arity selected the authority
mode without silently switching the current Context or publishing Memory
changes.
