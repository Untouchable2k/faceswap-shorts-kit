#!/usr/bin/env bash
# Opens the Face-Swap Studio (step-by-step app) in your browser.
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$KIT/tools/env/bin/python" "$KIT/studio.py" "$@"
