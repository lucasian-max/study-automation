#!/bin/bash
set -e

echo "=== Step 1: Get an OpenRouter API key ==="
echo "1. Go to https://openrouter.ai/keys"
echo "2. Sign in with GitHub (free, no credit card)"
echo "3. Copy your API key (sk-or-...)"
echo ""

read -p "Paste your OpenRouter API key: " OR_KEY

echo ""
echo "=== Step 2: Encode auth files ==="

if [ -f token.json ]; then
  TOKEN_B64=$(base64 -i token.json 2>/dev/null || base64 < token.json)
  echo "token.json encoded ✓"
else
  echo "Error: token.json not found. Run 'python3 main.py' locally first."
  exit 1
fi

if [ -f whatsapp-session/state.json ]; then
  WA_B64=$(base64 -i whatsapp-session/state.json 2>/dev/null || base64 < whatsapp-session/state.json)
  echo "whatsapp-session/state.json encoded ✓"
else
  echo "Warning: whatsapp-session/state.json not found — WhatsApp will be skipped in CI."
  echo "Run 'python3 main.py' locally and scan the QR code to generate it."
  WA_B64=""
fi

echo ""
echo "=== Step 3: Set GitHub secrets ==="
echo "Running: gh secret set ..."
echo ""

gh secret set OPENROUTER_API_KEY --repo lucasian-max/study-automation --body "$OR_KEY"
echo "OPENROUTER_API_KEY set ✓"

echo "$TOKEN_B64" | gh secret set TOKEN_JSON --repo lucasian-max/study-automation
echo "TOKEN_JSON set ✓"

if [ -n "$WA_B64" ]; then
  echo "$WA_B64" | gh secret set WHATSAPP_STATE --repo lucasian-max/study-automation
  echo "WHATSAPP_STATE set ✓"
fi

echo ""
echo "=== All secrets set! ==="
echo "The workflow will run daily at 11pm IST (17:30 UTC)."
echo "You can also trigger it manually at:"
echo "  https://github.com/lucasian-max/study-automation/actions"
echo ""
echo "To test immediately, run: gh workflow run daily.yml --repo lucasian-max/study-automation"
