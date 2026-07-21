"""Simple 10pm reminder — checks if entries logged, sends WhatsApp reminder."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from main import load_config, get_sheets_service, get_todays_entries, send_whatsapp, retry_fn

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

if entries:
    total_h = sum(float(e["hours"]) if e["hours"] else 0 for e in entries)
    msg = f"\u23f0 10pm check: {len(entries)} session(s) logged today ({total_h:.1f}h). Summary coming at 10:50pm!"
else:
    msg = f"\u23f0 10pm check: No study entries logged yet. Log them before 10:50pm or an alert will be sent."

try:
    send_whatsapp(msg, config)
    print("Reminder sent")
except Exception as e:
    print(f"WhatsApp failed: {e}")
