#!/bin/sh
# macOS bootstrap. Python and dependency isolation are owned by uv.
set -eu

package_spec=${MEMCOMMIT_PACKAGE:-memcommit @ https://github.com/ianarawjo/memcommit/archive/refs/heads/user-study-prototype.zip}
run_setup=1
update_shell=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        --package)
            if [ "$#" -lt 2 ]; then printf '%s\n' '--package requires a package specifier' >&2; exit 2; fi
            package_spec=$2; shift 2 ;;
        --no-setup) run_setup=0; shift ;;
        --no-shell-update) update_shell=0; shift ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
    esac
done
if [ "$(uname -s)" != Darwin ]; then
    printf 'This installer currently supports macOS.\n' >&2
    exit 1
fi
uv_binary=""
if [ -n "${MEMCOMMIT_UV_INSTALL_DIR:-}" ]; then
    if [ -x "$MEMCOMMIT_UV_INSTALL_DIR/uv" ]; then uv_binary="$MEMCOMMIT_UV_INSTALL_DIR/uv"; fi
else
    uv_binary=$(command -v uv || true)
fi
if [ -z "$uv_binary" ] && [ -z "${MEMCOMMIT_UV_INSTALL_DIR:-}" ]; then
    for candidate in "$HOME/.local/bin/uv" /opt/homebrew/bin/uv /usr/local/bin/uv; do
        if [ -x "$candidate" ]; then uv_binary=$candidate; break; fi
    done
fi
if [ -z "$uv_binary" ]; then
    installer=$(mktemp)
    trap 'rm -f "$installer"' EXIT HUP INT TERM
    curl -fsSL https://astral.sh/uv/install.sh -o "$installer"
    UV_NO_MODIFY_PATH=1 UV_INSTALL_DIR="${MEMCOMMIT_UV_INSTALL_DIR:-$HOME/.local/bin}" sh "$installer"
    uv_binary="${MEMCOMMIT_UV_INSTALL_DIR:-$HOME/.local/bin}/uv"
fi
"$uv_binary" tool install --upgrade --refresh --python "${MEMCOMMIT_PYTHON:-3.12}" "$package_spec"
tool_bin=$("$uv_binary" tool dir --bin)
if [ "$update_shell" -eq 1 ]; then "$uv_binary" tool update-shell; fi
PATH="$tool_bin:$PATH"
export PATH
"$tool_bin/mem" setup --status
if [ "$update_shell" -eq 1 ]; then
    printf 'Installed mem. New terminals will use the registered PATH.\n'
else
    printf 'Installed mem. Shell registration skipped; run uv tool update-shell to enable it.\n'
fi
if [ "$run_setup" -eq 1 ]; then
    if [ -t 0 ]; then
        "$tool_bin/mem" setup
    elif ( : </dev/tty ) 2>/dev/null; then
        "$tool_bin/mem" setup </dev/tty
    else
        printf 'Run mem setup in a terminal to choose a provider and create your first Profile.\n'
    fi
fi
