#!/bin/bash
# Emoticon post-hunt pipeline:
#   match key from hunted_keys.txt → save emoticon_key.txt
#   → decrypt emoticon.db → export CDN metadata + download images
#
# Prerequisite: sudo ./hunt.sh (open emoji panel so emoticon key is captured)
#
# Usage:
#   ./emoticon_pipeline.sh
#   ./emoticon_pipeline.sh --metadata-only
#   ./emoticon_pipeline.sh --key <64hex>
set -euo pipefail
cd "$(dirname "$0")"
exec python3 emoticon_pipeline.py "$@"
