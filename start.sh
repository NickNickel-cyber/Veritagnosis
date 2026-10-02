#!/usr/bin/env bash
# Veritagnosis - macOS / Linux launcher.
#
# Like run.bat, this only finds Python and hands over to start.py, so there
# is one implementation rather than three that drift apart.
#
#     ./start.sh          start the app
#     ./start.sh --dev    start with hot reload
#     ./start.sh --test   run the test suite
set -euo pipefail
cd "$(dirname "$0")"

for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    exec "$candidate" start.py "$@"
  fi
done

cat <<'MSG'

  Python was not found on this computer.

  Install Python 3.11 or newer:
      macOS:  brew install python@3.12
      Linux:  your package manager, e.g. sudo apt install python3

MSG
exit 1
