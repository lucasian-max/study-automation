# Study Automation Setup

## 1. Install dependencies

```bash
cd ~/study-automation
pip3 install -r requirements.txt
playwright install chromium
```

## 2. Google Sheets API setup (OAuth — no service account needed)

1. Go to https://console.cloud.google.com
2. Create a new project (or select existing)
3. Enable the **Google Sheets API**
4. Go to **Credentials → Create Credentials → OAuth client ID**
   - If it asks to configure consent screen first:
     - Choose **External** user type
     - Fill in app name ("Study Tracker"), your email
     - Skip scopes, skip test users, click **Back to Dashboard**
5. Now **Create Credentials → OAuth client ID**
   - Application type: **Desktop app**
   - Name: "Study Tracker CLI"
   - Click **Create**
6. Download the JSON → save as **`client_secret.json`** in `~/study-automation/`
7. Open your Google Sheet, verify you have access (your personal email is the owner)

### Get your Spreadsheet ID
From your sheet URL: `https://docs.google.com/spreadsheets/d/`**THIS_IS_THE_ID**`/edit`

## 3. Email (Gmail app password)

1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Copy the 16-character password

## 4. Configure

Edit `config.json` and fill in:
- `spreadsheet_id` — from step 2
- `group_name` — exact name of your WhatsApp group
- `recipient_jid` — your personal WhatsApp JID (e.g. `919876543210@s.whatsapp.net`). Messages are sent here instead of a group.
- `email.sender` — your Gmail address
- `email.app_password` — the 16-char app password

## 5. First run (authenticates Google + WhatsApp)

```bash
python3 main.py
```

Two things will happen in sequence:
- **First** — a browser tab opens asking you to log into Google (the OAuth consent screen). Allow access. The token is saved.
- **Then** — a browser opens WhatsApp Web. Scan the QR code with your phone. The session is saved.

Both tokens are cached — future runs are automatic.

## 6. Schedule with launchd (runs automatically daily)

Create `~/Library/LaunchAgents/com.study.automation.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.study.automation</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/mridulvijay/study-automation/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/mridulvijay/study-automation</string>
    <key>StandardOutPath</key>
    <string>/Users/mridulvijay/study-automation/log.txt</string>
    <key>StandardErrorPath</key>
    <string>/Users/mridulvijay/study-automation/error.log</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict>
            <key>Hour</key>
            <integer>20</integer>
            <key>Minute</key>
            <integer>00</integer>
        </dict>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.study.automation.plist
```

This runs the script every day at 8pm. If entries exist → WhatsApp. If not → email alert.

## 7. Testing (dry-run)

Preview the WhatsApp message without sending anything:

```bash
python3 main.py --dry-run
```

This reads today's entries from Google Sheets, generates summaries and the formatted message, and prints it to the terminal. Nothing is sent to WhatsApp or email.
