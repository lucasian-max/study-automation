import json
from datetime import date
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from main import (
    summarize_notes, analyze_notes, get_tone, update_streak,
    format_whatsapp_message, format_email_body, load_streak_data,
    send_email, STREAK_FILE,
)

# Simulate July 7 entries matching your Excel structure
test_entries = [
    {
        "date": "07/07/2026",
        "category": "Maths",
        "activity": "MathAcademy",
        "hours": "1",
        "focus": "7",
        "notes": "Just revision on prior content. I feel like my focus is getting better. The more I do the more it will sharpen.",
    },
    {
        "date": "07/07/2026",
        "category": "Maths",
        "activity": "Dr Du",
        "hours": "1.75",
        "focus": "9",
        "notes": "I watched the network theory online.",
    },
]

print("=" * 50)
print("DRY RUN — Simulating July 7")
print("=" * 50)

# Step 1: Summarize notes with Ollama
print("\n[1/4] Summarizing notes via Ollama...")
summaries = summarize_notes(test_entries)

# Step 2: Analyze what went well
print("\n[2/4] Analyzing notes...")
went_well, improve = analyze_notes(test_entries)

# Step 3: Update streak (fake today as 07/07)
# Temporarily save the real streak, restore after
real_streak = None
if STREAK_FILE.exists():
    real_streak = json.loads(STREAK_FILE.read_text())

print("\n[3/4] Computing tone and streak...")
streak_data = update_streak(test_entries)
tone_line = get_tone(test_entries, streak_data)

# Step 4: Format messages
print("\n[4/4] Formatting messages...")
whatsapp_msg = format_whatsapp_message(test_entries, summaries, tone_line)

print("\n" + "=" * 50)
print("📱 WHATSAPP MESSAGE")
print("=" * 50)
print(whatsapp_msg)

print("\n" + "=" * 50)
print("📧 EMAIL BODY")
print("=" * 50)
email_body = format_email_body(test_entries, summaries, tone_line, streak_data, went_well, improve)
print(email_body)

# Restore real streak
if real_streak:
    STREAK_FILE.write_text(json.dumps(real_streak))
else:
    STREAK_FILE.unlink(missing_ok=True)

print("\n" + "=" * 50)
print("Dry run complete — no messages were sent.")
print("=" * 50)
