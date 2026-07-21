import json
import os
import re
import subprocess
from datetime import datetime, date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
STREAK_FILE = Path(__file__).parent / "streak.json"

def retry_fn(fn, max_attempts=5, base_delay=30, label=""):
    import time
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            print(f"{label} attempt {attempt}/{max_attempts} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def get_sheets_service(config):
    gs = config["google_sheets"]
    token_file = Path(gs.get("token_file", "token.json"))
    creds_file = gs["credentials_file"]

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        print(f"OAuth token saved to {token_file}")

    return build("sheets", "v4", credentials=creds)


def get_all_sheet_names(service, spreadsheet_id):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [s["properties"]["title"] for s in sheet_metadata.get("sheets", [])]


def get_todays_entries(service, config):
    gs = config["google_sheets"]
    spreadsheet_id = gs["spreadsheet_id"]
    today_str = date.today().strftime("%d/%m/%Y")

    sheet_names = get_all_sheet_names(service, spreadsheet_id)
    entries = []

    for sheet_name in sheet_names:
        range_name = f"{sheet_name}!A:F"
        try:
            result = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueRenderOption="FORMATTED_VALUE",
                )
                .execute()
            )
        except HttpError:
            continue

        rows = result.get("values", [])
        if not rows or len(rows) <= gs["header_row_count"]:
            continue

        data_rows = rows[gs["header_row_count"]:]
        for row in data_rows:
            if len(row) < 6:
                continue
            try:
                raw_date = row[gs["date_column"]]
            except IndexError:
                continue
            raw_date = raw_date.strip() if raw_date else ""
            try:
                parsed = datetime.strptime(raw_date, "%d/%m/%Y").date()
            except ValueError:
                try:
                    parsed = datetime.strptime(raw_date, "%m/%d/%Y").date()
                except ValueError:
                    continue
            if parsed == date.today():
                def _get(idx):
                    try:
                        return row[idx] if row[idx] else ""
                    except IndexError:
                        return ""
                entries.append({
                    "date": raw_date,
                    "category": _get(gs["category_column"]),
                    "activity": _get(gs["activity_column"]),
                    "hours": _get(gs["hours_column"]),
                    "focus": _get(gs["focus_column"]),
                    "notes": _get(gs["notes_column"]),
                })
    return entries


def _llm(prompt, timeout=60):
    import urllib.request, ssl
    import json as _json

    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()

    token = os.environ.get("OPENROUTER_API_KEY")
    if token:
        body = _json.dumps({
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 300,
        }).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "HTTP-Referer": "https://github.com/lucasian-max/study-automation",
            }
        )
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=timeout)
            data = _json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"OpenRouter error: {e}")

    # Fallback to local Ollama
    body = _json.dumps({"model": "llama3.2:3b", "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request("http://localhost:11434/api/generate", data=body, headers={"Content-Type": "application/json"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        data = _json.loads(resp.read())
        return data.get("response", "").strip()
    except Exception as e:
        print(f"Ollama error: {e}")
        return ""


def summarize_notes(entries):
    if not entries:
        return []

    EMOTIONAL = re.compile(r'(?i)(\bconcentrat\w*|\bconfiden\w*|\banxi\w*|\bnervous\w*|\bscared\w*|\bfeel(?:ing|ings)?\b|\bemotion\w*|\bworry\w*|\bstress\w*|\bmotivat\w*|\bprogress\w*|\bsharpening\b|\bconcern\w*|\bsurpris\w*|\buneasy\b|\bspook\w*|\bunsettl\w*|\bfrustrat\w*|\bdoubt\w*|\boverwhelm\w*|\bdisappoint\w*)')
    STOPWORDS = {'i', 'me', 'my', 'we', 'our', 'you', 'your', 'he', 'she', 'it', 'they', 'them',
                 'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
                 'by', 'from', 'up', 'about', 'into', 'over', 'after', 'before', 'between', 'under',
                 'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
                 'do', 'does', 'did', 'doing', 'will', 'would', 'can', 'could', 'shall', 'should',
                 'may', 'might', 'must', 'need', 'dare', 'ought', 'used', 'this', 'that', 'these',
                 'those', 'some', 'any', 'no', 'not', 'none', 'each', 'every', 'all', 'both',
                 'few', 'several', 'many', 'much', 'more', 'most', 'little', 'less', 'least',
                 'here', 'there', 'then', 'than', 'too', 'very', 'just', 'also', 'only', 'now',
                 'today', 'tomorrow', 'yesterday', 'get', 'got', 'gotten', 'make', 'made',
                 'take', 'took', 'go', 'went', 'gone', 'come', 'came', 'give', 'gave', 'look',
                 'see', 'saw', 'know', 'knew', 'think', 'thought', 'want', 'say', 'said', 'tell',
                 'told', 'ask', 'asked', 'try', 'tried', 'let', 'put', 'set', 'use', 'used',
                 'like', 'just', 'even', 'still', 'well', 'back', 'really', 'actually', 'also',
                 'next', 'first', 'last', 'while', 'during', 'since', 'because', 'if', 'when',
                 'where', 'how', 'what', 'which', 'who', 'whom', 'whose', 'why'}

    results = []
    for e in entries:
        note = e["notes"].strip() if e["notes"] else ""
        words = note.split()
        if len(words) < 5:
            results.append(note)
            continue

        emotional_count = len(EMOTIONAL.findall(note))
        if emotional_count >= 2 or (len(words) > 0 and emotional_count / len(words) > 0.2):
            results.append(e["activity"])
            continue

        prompt = f"Fix grammar, reply with only the corrected version: {note}"
        raw = _llm(prompt)
        cleaned = raw.strip("* ").strip("- ").strip().strip('"').strip("'")
        cleaned = re.sub(r'^[^:]+:\s*', '', cleaned).strip()
        # Drop any analysis/explanation the model adds
        parts = re.split(r'\n\s*\n', cleaned)
        cleaned = parts[0].strip()
        if not cleaned or len(cleaned) < 5:
            results.append(e["activity"])
            continue

        orig_keywords = {w.lower().strip(".,!?;:'\"") for w in words
                         if len(w) >= 5 and w.lower() not in STOPWORDS and not EMOTIONAL.search(w)}
        clean_keywords = {w.lower().strip(".,!?;:'\"") for w in cleaned.split()
                          if len(w) >= 5 and w.lower() not in STOPWORDS and not EMOTIONAL.search(w)}
        if orig_keywords and clean_keywords:
            if not (orig_keywords & clean_keywords):
                results.append(e["activity"])
                continue

        results.append(cleaned)

    return results


def analyze_notes(entries):
    if not entries:
        return "", ""

    notes_text = "\n".join(
        f"- {e['category']} ({e['activity']}): {e['notes']}"
        for e in entries if e.get("notes", "").strip()
    )

    # If notes are too short, skip analysis to avoid hallucination
    words = notes_text.split()
    if len(words) < 10:
        return "", ""

    prompt = f"From my notes, what went well and what to improve? One sentence each.\n\n{notes_text}"

    print("\n--- Analysis prompt ---")
    print(prompt)
    print("---")

    raw = _llm(prompt)
    print("LLM response:", raw)

    went_well = ""
    improve = ""
    for line in raw.split("\n"):
        lower = line.lower()
        if "went well" in lower and ":" in line:
            went_well = line.split(":", 1)[1].strip()
        elif "improve" in lower and ":" in line:
            improve = line.split(":", 1)[1].strip()

    return went_well, improve


def load_streak_data():
    if STREAK_FILE.exists():
        try:
            with open(STREAK_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"streak": 0, "last_date": None, "history": []}


def save_streak_data(data):
    with open(STREAK_FILE, "w") as f:
        json.dump(data, f)


def update_streak(entries):
    data = load_streak_data()
    today_str = date.today().strftime("%d/%m/%Y")

    if not entries:
        return data

    if data["last_date"]:
        try:
            last = datetime.strptime(data["last_date"], "%d/%m/%Y").date()
            diff = (date.today() - last).days
            if diff == 1:
                data["streak"] += 1
            elif diff > 1:
                data["streak"] = 1
        except ValueError:
            data["streak"] = 1
    else:
        data["streak"] = 1

    data["last_date"] = today_str

    total_hours = sum(_fval(e["hours"]) for e in entries)
    avg_focus = sum(_fval(e["focus"]) for e in entries) / max(len(entries), 1)

    data["history"].append({
        "date": today_str,
        "total_hours": round(total_hours, 1),
        "avg_focus": round(avg_focus, 1),
    })

    if len(data["history"]) > 60:
        data["history"] = data["history"][-60:]

    save_streak_data(data)
    return data


def get_tone(entries, streak_data):
    total_hours = sum(_fval(e["hours"]) for e in entries)
    avg_focus = sum(_fval(e["focus"]) for e in entries) / max(len(entries), 1)
    streak = streak_data.get("streak", 0)

    if streak >= 7:
        streak_line = f"Day {streak} of your study streak! 🔥"
    elif streak >= 3:
        streak_line = f"Day {streak} streak \u2014 keep it rolling! \U0001f4aa"
    elif streak > 1:
        streak_line = f"Day {streak} in a row! Nice."
    elif streak == 1:
        streak_line = "Back at it! Day 1 \U0001f504"
    else:
        streak_line = ""

    if total_hours >= 3 and avg_focus >= 8:
        tone = "Killed it today \U0001f525"
    elif total_hours >= 2:
        tone = "Solid session \U0001f4c8"
    elif total_hours >= 1:
        tone = "Good effort \U0001f44f"
    else:
        tone = "Every bit counts \U0001f422"

    hours_vs_yesterday = ""
    if streak_data["history"] and len(streak_data["history"]) >= 2:
        prev_hours = streak_data["history"][-2]["total_hours"]
        diff = round(total_hours - prev_hours, 1)
        if diff > 0:
            hours_vs_yesterday = f"Up {diff}h from yesterday \u2191"
        elif diff < 0:
            hours_vs_yesterday = f"Down {abs(diff)}h from yesterday \u2193"

    parts = [t for t in [streak_line, tone, hours_vs_yesterday] if t]
    return " | ".join(parts)


def compute_weekly_stats(streak_data):
    history = streak_data.get("history", [])
    if not history:
        return ""

    recent = history[-7:]
    week_hours = sum(d["total_hours"] for d in recent)
    week_focus = sum(d["avg_focus"] for d in recent) / max(len(recent), 1)
    study_days = sum(1 for d in recent if d["total_hours"] > 0)

    lines = [f"This week ({len(recent)} days tracked):"]
    lines.append(f"  Total: {week_hours:.1f}h across {study_days} days")
    lines.append(f"  Avg focus: {week_focus:.0f}/10")
    lines.append(f"  Daily avg: {week_hours/max(len(recent),1):.1f}h/day")

    if len(history) >= 7:
        prev = history[-14:-7] if len(history) >= 14 else history[:7]
        if prev:
            prev_week_hours = sum(d["total_hours"] for d in prev)
            diff = round(week_hours - prev_week_hours, 1)
            if diff > 0:
                lines.append(f"  Up {diff}h from last week \U0001f4c8")
            elif diff < 0:
                lines.append(f"  Down {abs(diff)}h from last week \U0001f4c9")
            else:
                lines.append("  Same as last week")

    return "\n".join(lines)


def compute_monthly_stats(streak_data):
    history = streak_data.get("history", [])
    if not history:
        return ""

    current_month = date.today().month
    current_year = date.today().year
    month_entries = []
    for d in history:
        try:
            d_date = datetime.strptime(d["date"], "%d/%m/%Y").date()
            if d_date.month == current_month and d_date.year == current_year:
                month_entries.append(d)
        except ValueError:
            continue

    if not month_entries:
        return ""

    total_hours = sum(d["total_hours"] for d in month_entries)
    avg_focus = sum(d["avg_focus"] for d in month_entries) / max(len(month_entries), 1)
    study_days = sum(1 for d in month_entries if d["total_hours"] > 0)

    month_name = date.today().strftime("%B")
    lines = [f"{month_name} so far ({len(month_entries)} days tracked):"]
    lines.append(f"  Total: {total_hours:.1f}h across {study_days} days")
    lines.append(f"  Avg focus: {avg_focus:.0f}/10")
    lines.append(f"  Daily avg: {total_hours/max(len(month_entries),1):.1f}h/day")

    return "\n".join(lines)


def _fval(val):
    if val is None:
        return 0.0
    if isinstance(val, bool):
        return float(val)
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().lower().replace("hrs", "").replace("h", "").strip()
    if not s:
        return 0.0
    try:
        v = float(s)
        return v if v == v else 0.0
    except (ValueError, TypeError):
        return 0.0

def _fdisp(val, suffix=""):
    if val is None:
        return f"-{suffix}"
    s = str(val).strip()
    if not s:
        return f"-{suffix}"
    cleaned = s.lower().replace("hrs", "").replace("h", "").strip()
    try:
        v = float(cleaned)
    except ValueError:
        return f"-{suffix}"
    return f"{v:.1f}{suffix}" if v == int(v) else f"{v}{suffix}"

def format_whatsapp_message(entries, summaries, tone_line):
    total_hours = sum(_fval(e["hours"]) for e in entries)
    avg_focus = sum(_fval(e["focus"]) for e in entries) / max(len(entries), 1)

    cat_counts = {}
    for e in entries:
        c = e["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    cat_line = ", ".join(f"{c} ({n})" for c, n in cat_counts.items())

    lines = [f"\U0001f4da *Study Summary \u2014 {date.today().strftime('%d %b %Y')}*"]
    lines.append(f"_{len(entries)} sessions \u00b7 {total_hours:.1f}h total \u00b7 avg focus {avg_focus:.0f}/10_\n")
    lines.append(f"{tone_line}\n")

    for i, e in enumerate(entries):
        s = summaries[i] if i < len(summaries) and summaries[i] else ""
        hours_disp = _fdisp(e["hours"], "h")
        focus_disp = _fdisp(e["focus"])
        lines.append(
            f"*{i+1}. {e['category']} \u2014 {e['activity']}*"
            f"\n   \u23f1 {hours_disp}  |  \U0001f3af {focus_disp}/10"
        )
        if s:
            lines.append(f"   _{s}_")
        lines.append("")

    lines.append(f"Categories: {cat_line}")

    return "\n".join(lines)


def format_email_body(entries, summaries, tone_line, streak_data, went_well, improve):
    total_hours = sum(_fval(e["hours"]) for e in entries)
    avg_focus = sum(_fval(e["focus"]) for e in entries) / max(len(entries), 1)
    today_str = date.today().strftime('%d %b %Y')

    weekly = compute_weekly_stats(streak_data)
    monthly = compute_monthly_stats(streak_data)

    parts = [f"Daily Study Report \u2014 {today_str}"]
    parts.append("")
    parts.append(tone_line)
    parts.append("")
    parts.append(f"Today: {total_hours:.1f}h | {len(entries)} sessions | Focus: {avg_focus:.0f}/10")
    parts.append("")

    parts.append("Sessions")
    for i, e in enumerate(entries):
        s = summaries[i] if i < len(summaries) and summaries[i] else ""
        full_note = e.get("notes", "").strip()
        hours_disp = _fdisp(e["hours"], "h")
        focus_disp = _fdisp(e["focus"])
        parts.append(f"  {i+1}. {e['category']} \u2014 {e['activity']} ({hours_disp}, focus {focus_disp}/10)")
        if s:
            parts.append(f"     Summary: {s}")
        if full_note:
            parts.append(f"     Note: {full_note}")
        parts.append("")

    if went_well or improve:
        parts.append("Reflection")
        if went_well:
            parts.append(f"  What went well: {went_well}")
        if improve:
            parts.append(f"  To improve: {improve}")
        parts.append("")

    if weekly:
        parts.append("Weekly View")
        parts.append(weekly)
        parts.append("")

    if monthly:
        parts.append("Monthly View")
        parts.append(monthly)
        parts.append("")

    return "\n".join(parts)


def send_email(subject, body, config):
    import smtplib
    from email.mime.text import MIMEText

    email_cfg = config["email"]

    def _do():
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = email_cfg["sender"]
        msg["To"] = email_cfg["recipient"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_cfg["sender"], email_cfg["app_password"])
            server.send_message(msg)
        print(f"Email sent to {email_cfg['recipient']}")

    retry_fn(_do, max_attempts=3, base_delay=10, label="Email")


def send_email_alert(config):
    today_str = date.today().strftime("%d %b %Y")
    streak_data = load_streak_data()
    streak = streak_data.get("streak", 0)

    alert = f"Hi,\n\nNo study entries were logged for {today_str}."
    if streak > 1:
        alert += f"\n\nYour {streak}-day streak was broken."
    alert += "\n\nGet back on track tomorrow!\n\n\u2014 Study Tracker Bot"

    send_email(f"No study logged \u2014 {today_str}", alert, config)


def send_whatsapp(message, config):
    import asyncio, sys
    from playwright.async_api import async_playwright
    IN_CI = os.environ.get("CI") == "true"

    async def _send():
        wp = config["whatsapp"]
        group_name = wp["group_name"]
        session_dir = Path(wp["session_dir"])
        session_dir.mkdir(exist_ok=True)
        state_file = session_dir / "state.json"

        if not state_file.exists() and IN_CI:
            print("WhatsApp session not found and running in CI — skipping WhatsApp, will send email instead")
            raise RuntimeError("NO_SESSION_IN_CI")

        async with async_playwright() as p:
            if IN_CI:
                browser = await p.chromium.launch(
                    headless=False,
                    args=[
                        "--no-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-gpu",
                        "--window-size=1280,720",
                    ]
                )
            elif sys.platform == "darwin":
                browser = await p.chromium.launch(
                    headless=False, channel="chrome",
                    args=["--disable-blink-features=AutomationControlled"]
                )
            else:
                browser = await p.chromium.launch(headless=False)

            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 720},
            } if IN_CI else {}
            if state_file.exists():
                context_kwargs["storage_state"] = str(state_file)

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            # Stealth: hide automation
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
            """)

            print("Opening WhatsApp Web...")
            await page.goto("https://web.whatsapp.com", wait_until="load")

            if not state_file.exists():
                print("\nWhatsApp Web is open in your browser.")
                print("Scan the QR code with your phone, then press ENTER here.")
                input("Press ENTER after scanning...")
                await page.wait_for_timeout(3000)
                await context.storage_state(path=str(state_file))
                print("Session saved.\n")

            print("Waiting for chat to load...")
            try:
                await page.wait_for_selector('[aria-placeholder]', timeout=45000)
            except Exception as e:
                await page.screenshot(path=str(Path.cwd() / "wa_debug.png"), full_page=True)
                raise
            await page.wait_for_timeout(2000)

            print(f"Searching for group: {group_name}")

            search_box = page.get_by_role("textbox", name="Search")
            await search_box.click()
            await search_box.fill(group_name)
            await page.wait_for_timeout(2000)

            group_locator = page.locator(f"span[title='{group_name}']").first
            await group_locator.wait_for(timeout=10000)
            await group_locator.click()
            await page.wait_for_timeout(1500)

            msg_area = page.locator("footer div[contenteditable='true']").first
            await msg_area.wait_for(timeout=10000)
            await msg_area.click()
            await page.keyboard.type(message, delay=10)
            await page.wait_for_timeout(1000)

            send_btn = page.locator("button span[data-icon='send']").first
            await send_btn.wait_for(timeout=5000)
            await send_btn.click()
            await page.wait_for_timeout(3000)

            print("Message sent!")
            await browser.close()

    def _run():
        asyncio.run(_send())

    n = 2 if IN_CI else 5
    retry_fn(_run, max_attempts=n, base_delay=30, label="WhatsApp")


def main():
    config = load_config()
    try:
        service = retry_fn(lambda: get_sheets_service(config), max_attempts=3, base_delay=10, label="Sheets auth")
    except Exception as e:
        print(f"Google Sheets auth failed after retries: {e}")
        return

    try:
        entries = retry_fn(lambda: get_todays_entries(service, config), max_attempts=3, base_delay=10, label="Sheets read")
    except Exception as e:
        print(f"Failed to read sheet after retries: {e}")
        return

    if entries:
        print(f"Found {len(entries)} entries for today")

        summaries = summarize_notes(entries)
        went_well, improve = analyze_notes(entries)
        streak_data = update_streak(entries)
        tone_line = get_tone(entries, streak_data)

        whatsapp_msg = format_whatsapp_message(entries, summaries, tone_line)
        print("\n--- WhatsApp Message ---")
        print(whatsapp_msg)
        print("---\n")

        wa_ok = False
        try:
            send_whatsapp(whatsapp_msg, config)
            wa_ok = True
        except Exception as e:
            print(f"WhatsApp failed after retries: {e}")
            try:
                alert = f"WhatsApp message failed to send.\n\nOriginal message:\n\n{whatsapp_msg}\n\nError: {e}"
                send_email(f"CRITICAL: WhatsApp failed \u2014 {date.today().strftime('%d %b %Y')}", alert, config)
                print("Critical alert email sent.")
            except Exception as e2:
                print(f"Even critical email failed: {e2}")

        email_body = format_email_body(entries, summaries, tone_line, streak_data, went_well, improve)
        print("\n--- Email Body ---")
        print(email_body)
        print("---\n")

        today_str = date.today().strftime('%d %b %Y')
        try:
            send_email(f"Study Report \u2014 {today_str}", email_body, config)
        except Exception as e:
            print(f"Email failed: {e}")
    else:
        print("No entries found for today. Sending alert email...")
        try:
            send_email_alert(config)
        except Exception as e:
            print(f"Email alert failed: {e}")

    print("Done!")


if __name__ == "__main__":
    main()
