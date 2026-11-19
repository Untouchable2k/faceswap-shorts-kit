#!/usr/bin/env bash
# Swap your face into every video in ./clips -> ./output. Extra options: bash swap_linux.sh --help
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$KIT/tools/env/bin/python" "$KIT/swap.py" "$@"
