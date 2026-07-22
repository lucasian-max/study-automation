#!/bin/bash
cd "$(dirname "$0")/.."
python3 scripts/save_profile.py
echo ""
echo "Press ENTER to close this window..."
read
