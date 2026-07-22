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

echo ""
echo "=== Step 3: Set GitHub secrets ==="
echo "Running: gh secret set ..."
echo ""

gh secret set OPENROUTER_API_KEY --repo lucasian-max/study-automation --body "$OR_KEY"
echo "OPENROUTER_API_KEY set ✓"

echo "$TOKEN_B64" | gh secret set TOKEN_JSON --repo lucasian-max/study-automation
echo "TOKEN_JSON set ✓"

read -p "Paste your Gmail app password (or press Enter to skip): " GMAIL_PW
if [ -n "$GMAIL_PW" ]; then
  echo "$GMAIL_PW" | gh secret set GMAIL_APP_PASSWORD --repo lucasian-max/study-automation
  echo "GMAIL_APP_PASSWORD set ✓"
else
  echo "Warning: GMAIL_APP_PASSWORD not set — email delivery will fail in CI."
  echo "Generate one at https://myaccount.google.com/apppasswords"
fi

echo ""
echo "=== All secrets set! ==="
echo "The workflow will run daily at 11pm IST (17:30 UTC)."
echo "You can also trigger it manually at:"
echo "  https://github.com/lucasian-max/study-automation/actions"
echo ""
echo "To test immediately, run: gh workflow run daily.yml --repo lucasian-max/study-automation"
