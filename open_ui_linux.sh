#!/usr/bin/env bash
# Opens the FaceFusion web interface in your browser (for previewing / fine-tuning one clip).
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$KIT/tools/env/bin/python" "$KIT/swap.py" --ui
