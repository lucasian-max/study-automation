"""10pm email reminder — checks if entries logged, sends email."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from main import load_config, get_sheets_service, get_todays_entries, send_email, retry_fn
from datetime import date

config = load_config()
try:
    service = retry_fn(lambda: get_sheets_service(config), max_attempts=3, base_delay=10, label="Sheets auth")
except Exception as e:
    print(f"Auth failed: {e}")
    sys.exit(1)

try:
    entries = retry_fn(lambda: get_todays_entries(service, config), max_attempts=3, base_delay=10, label="Sheets read")
except Exception as e:
    print(f"Read failed: {e}")
    sys.exit(1)

today_str = date.today().strftime('%d %b %Y')

if entries:
    total_h = sum(float(e["hours"]) if e["hours"] else 0 for e in entries)
    lines = [f"10pm check \u2014 {today_str}"]
    lines.append("")
    lines.append(f"Good, you logged {len(entries)} session(s) today ({total_h:.1f}h total). Keep going.")
    lines.append("")
    for e in entries:
        lines.append(f"  \u2022 {e['category']} \u2014 {e['activity']} ({e['hours']}h)")
    lines.append("")
    lines.append("Summary goes to WhatsApp at 10:50pm.")
    subject = f"\u2705 Study check-in \u2014 {len(entries)} session(s)"
else:
    lines = [f"10pm check \u2014 {today_str}"]
    lines.append("")
    lines.append("WHERE THE HELL IS YOUR WORK? DO WORK.")
    lines.append("")
    lines.append("You have until 10:50pm to log your study entries. If nothing is logged by then, another alert will be sent and your streak will be broken.")
    lines.append("")
    lines.append("Stop procrastinating and get to it.")
    subject = f"\u26a0\ufe0f NO STUDY LOGGED \u2014 WHERE IS YOUR WORK"

try:
    send_email(subject, "\n".join(lines), config)
    print("Reminder email sent")
except Exception as e:
    print(f"Email failed: {e}")
