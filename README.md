# 📞 TWILIO-PBX

A Flask-based PBX (Private Branch Exchange) system using Twilio and Gunicorn, designed to run as a reliable background service via `systemd`. It provides a dynamic IVR (Interactive Voice Response) menu where callers can connect to team members, hear automated messages, or leave voicemails that are saved and emailed to specified recipients.

---

## 🚀 Features

- **Dynamic IVR Extension Menu**
  - Configure extension actions with a single Python dictionary.
- **Extension Types**
  - `dial_external`: Connects the caller to a real phone number.
  - `voicemail`: Records voicemail, saves it locally, and emails it.
  - `info_message`: Plays an automated voice message and ends the call.
- **Voicemail Emailing**
  - Automatically sends the recording (WAV/MP3) as an email attachment.
- **Secure Folder Storage**
  - Organized voicemail files in extension-specific folders.
- **Production-Ready with systemd**
  - Runs via Gunicorn and systemd for high availability and startup on boot.

---

## 📁 Project Structure

```
/opt/pbx_app/
├── venv/                   # Python virtual environment
├── pbx_script_v3.py        # Main Flask application
├── requirements.txt        # Python dependencies
├── voicemails/             # Stored voicemail recordings
│   ├── general/
│   │   └── <timestamp>_<caller>_<sid>.wav
│   └── billing/
│       └── <timestamp>_<caller>_<sid>.wav
└── pbx_app.service          # systemd service configuration (in /etc/systemd/system)
```

---

## ⚙️ Setup Instructions

### 1. Prerequisites

- Python 3 and `pip`
- Twilio Account + Voice-enabled Phone Number
- SMTP-capable Email Account
- (Optional) [ngrok](https://ngrok.com/download) for local testing

> **Gmail Note**: If using 2FA, you must generate an "App Password" from your [Google Account](https://myaccount.google.com/security).

---

### 2. Prepare the App Directory

```bash
sudo mkdir -p /opt/pbx_app
cd /opt/pbx_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

---

### 3. Place Application Files

Copy the following into `/opt/pbx_app`:

```bash
sudo cp pbx_script_v3.py /opt/pbx_app/
sudo cp requirements.txt /opt/pbx_app/
```

---

### 4. Configure `pbx_script_v3.py`

```bash
sudo nano /opt/pbx_app/pbx_script_v3.py
```

Update:

- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SENDER_EMAIL`
- `EXTENSIONS`: Update phone numbers and email addresses

Save and exit.

---

### 5. Create Dedicated System User

```bash
sudo useradd --system --no-create-home --shell /bin/false pbxuser
```

---

### 6. Set File Permissions

```bash
sudo chown -R pbxuser:pbxuser /opt/pbx_app
```

---

### 7. Create `systemd` Service

```bash
sudo nano /etc/systemd/system/pbx_app.service
```

Paste:

```ini
[Unit]
Description=Flask PBX Application
After=network.target syslog.target

[Service]
User=pbxuser
Group=pbxuser
WorkingDirectory=/opt/pbx_app
ExecStart=/opt/pbx_app/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 pbx_script_v3:app
Restart=always
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Save and close.

---

### 8. Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable pbx_app.service
sudo systemctl start pbx_app.service
```

---

### 9. Check Logs and Status

```bash
sudo systemctl status pbx_app.service
sudo journalctl -u pbx_app.service -f
```

---

### 10. Configure Twilio Webhook (Testing)

**Using ngrok:**

```bash
ngrok http 5000
```

Copy the forwarding URL (e.g., `https://abc123.ngrok-free.app`)

**In Twilio Console:**

1. Go to **Phone Numbers > Manage > Active Numbers**
2. Select your number
3. Under **Voice & Fax**, set:
   - **Webhook**: `https://<ngrok-url>/incoming_call`
   - **HTTP Method**: `POST`
4. Save

---

### 11. Test the PBX

- Call your Twilio number.
- Press:
  - `101`, `102` → Connect to external numbers
  - `103`, `105` → Leave a voicemail
  - `104` → Hear an info message
- Verify:
  - Voicemails are saved under `/opt/pbx_app/voicemails/<type>/`
  - Emails are sent to recipients with attachments

---

## 🛠️ Managing the Service

```bash
sudo systemctl stop pbx_app.service      # Stop
sudo systemctl start pbx_app.service     # Start
sudo systemctl restart pbx_app.service   # Restart (e.g., after editing code)
sudo systemctl disable pbx_app.service   # Disable on boot
```

---

## 📌 Notes

- All voicemail recordings are saved with the format:  
  `<timestamp>_<caller_number>_<twilio_call_sid>.wav`
- System logs available via `journalctl`.
- You may integrate `.env` and `python-dotenv` for cleaner config separation.
