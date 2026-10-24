#!/bin/bash
# ===================================================================
#  Veritagnosis - double-click this on macOS (or Linux).
#
#  macOS opens .command files in Terminal and runs them, which is why
#  this is not called .sh: a .sh file opens in a text editor instead.
#
#  It finds Python, sets the app up the first time, and starts it.
#
#  Options, if you ever want them:
#      ./Veritagnosis.command dev     reload automatically while editing
#      ./Veritagnosis.command reset   rebuild the web page from scratch
#
#  Windows users: use Veritagnosis.bat instead.
# ===================================================================
set -u

# Double-clicking in Finder starts in the user's home directory, not here,
# so the script has to find its own folder before anything else.
cd "$(dirname "$BASH_SOURCE")" || exit 1

printf '\033]0;Veritagnosis\007'   # name the Terminal window

for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    # Reject a Python that is too old before handing over, so the message
    # mentions Python rather than a syntax error from inside start.py.
    if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>/dev/null; then
      "$candidate" start.py "$@"
      code=$?
      if [ $code -ne 0 ]; then
        echo
        read -r -p "  Something went wrong. Press Enter to close. " _
      fi
      exit $code
    fi
  fi
done

cat <<'MSG'

  Python 3.11 or newer is not installed on this computer.

  Veritagnosis needs it.

    macOS:  download the installer from
              https://www.python.org/downloads/macos/
            open it, click through, then double-click
            Veritagnosis.command again.

    Linux:  install it with your package manager, for example
              sudo apt install python3 python3-venv

MSG
read -r -p "  Press Enter to close. " _
exit 1
