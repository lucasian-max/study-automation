#!/bin/bash
# Run this script locally to generate the GitHub secrets
# Usage: bash scripts/setup.sh

set -e

echo "=== Step 1: Create GitHub PAT ==="
echo "Go to: https://github.com/settings/tokens"
echo "Create a classic token with scopes: repo, models"
echo "Copy the token value."
echo ""

read -p "Paste your GitHub PAT (classic, with models scope): " GH_PAT

echo ""
echo "=== Step 2: Encode auth files ==="

TOKEN_B64=$(base64 -i token.json 2>/dev/null || base64 < token.json)
echo "Token JSON encoded ✓"

if [ -f whatsapp-session/state.json ]; then
  WA_B64=$(base64 -i whatsapp-session/state.json 2>/dev/null || base64 < whatsapp-session/state.json)
  echo "WhatsApp session encoded ✓"
else
  echo "Warning: whatsapp-session/state.json not found. Run main.py locally first to generate it."
  WA_B64=""
fi

echo ""
echo "=== Step 3: Set GitHub secrets ==="
echo "Run these commands:"
echo ""
echo "echo \"$TOKEN_B64\" | gh secret set TOKEN_JSON --repo lucasian-max/study-automation"
echo "gh secret set GH_PAT --repo lucasian-max/study-automation --body \"$GH_PAT\""
if [ -n "$WA_B64" ]; then
  echo "echo \"$WA_B64\" | gh secret set WHATSAPP_STATE --repo lucasian-max/study-automation"
fi
