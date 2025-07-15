# TWILIO-PBX

This project implements a simple PBX (Private Branch Exchange) system using Flask, Twilio, and Gunicorn, designed to run as a systemd service. It allows callers to interact with an IVR (Interactive Voice Response) menu, connect to extensions, or leave voicemails which are then stored locally and emailed to the designated recipient.

## Features

*   **Dynamic Extension Configuration:** Easily add, modify, or remove extensions by editing a Python dictionary.
*   **Multiple Extension Types:**
    *   `dial_external`: Connects the caller to an external phone number.
    *   `voicemail`: Records a voicemail, saves it to a categorized folder, and emails the recording to a specified recipient.
    *   `info_message`: Plays a predefined message and hangs up.
*   **Systemd Integration:** Configured to run reliably in the background and start automatically on system boot using Gunicorn and systemd.
*   **Voicemail Storage & Email Notification:** Stores WAV/MP3 files in extension-specific directories and sends them as email attachments.

## Project Structure

Once set up, your project directory will look something like this:

```bash
/opt/pbx_app/
├── venv/ # Python virtual environment
├── pbx_script_v3.py # Main Flask application script
├── requirements.txt # Python dependencies
├── voicemails/ # Directory for stored voicemails
│ ├── general/ # Voicemails for general extension
│ │ └── <timestamp><caller><sid>.wav
│ └── billing/ # Voicemails for billing extension
│ └── <timestamp><caller><sid>.wav
└── pbx_app.service # systemd service configuration (lives in /etc/systemd/system)
```

## Setup Instructions

Follow these steps to set up and run your PBX application.

### 1. Prerequisites

*   **Python 3:** Installed on your Linux server (e.g., Ubuntu, Debian, CentOS).
*   **`pip`:** Python package installer.
*   **Twilio Account & Phone Number:** A Twilio account with a voice-enabled phone number.
*   **Email Account for Sending:** An email address and its SMTP server details (e.g., Gmail, Outlook, Yahoo) to send voicemail notifications.
    *   **Gmail users:** If you have 2-Factor Authentication (2FA) enabled, you *must* generate an **App password** for your email account to use instead of your regular password. Find this in your Google Account security settings.
*   **`ngrok` (for local testing):** Download and set up from [ngrok.com/download](https://ngrok.com/download) if you are testing from your local machine. This is not needed for production deployment with Nginx/Apache.

### 2. Prepare Your Application Directory

Create a dedicated directory for your application on your server and set up a Python virtual environment.

```bash
# Create a dedicated directory for your application
sudo mkdir -p /opt/pbx_app

# Navigate into the directory
cd /opt/pbx_app

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install Flask, Twilio, Gunicorn, and Requests using the requirements file
pip install -r requirements.txt

# Deactivate the virtual environment (optional, you'll be running via systemd soon)
deactivate
```


### 3. Place Application Files
Place the `pbx_script_v3.py` and `requirements.txt` files into the `/opt/pbx_app` directory.

```bash
# Assuming you are in the directory where you saved the files, e.g., your home folder
sudo cp pbx_script_v3.py /opt/pbx_app/
sudo cp requirements.txt /opt/pbx_app/
```

### 4. Crucial Configuration: Edit `pbx_script_v3.py`
Before proceeding, you MUST edit `pbx_script_v3.py` to enter your sensitive details.

Open the file for editing:

```bash
sudo nano /opt/pbx_app/pbx_script_v3.py
```

Locate and update the following sections:

```bash
`SMTP_SERVER`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SENDER_EMAIL`: Your email sending credentials.
`EXTENSIONS` dictionary:
For `dial_external` types, update `target` phone numbers to real numbers.
For `voicemail` types, update `voicemail_recipient_email` to the actual email addresses where you want voicemails sent.
Save and close the file (Ctrl+O, Enter, Ctrl+X in nano).
```

### 5. Create a Dedicated User (Recommended for Security)
Create a system user that your application will run under. This user won't have login capabilities.

```bash
sudo useradd --system --no-create-home --shell /bin/false pbxuser
```

### 6. Set File Permissions
Give the `pbxuser` ownership of your application directory, ensuring it can create voicemail folders and files.

```bash
sudo chown -R pbxuser:pbxuser /opt/pbx_app
```

### 7. Create the Systemd Service File
Create a new service file for `systemd` which tells it how to start, stop, and manage your application.

```bash
sudo nano /etc/systemd/system/pbx_app.service
```

Paste the following content into the file:

```bash
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
# Set environment variables if needed, e.g., for sensitive keys (better to use .env and python-dotenv)
# Environment="MY_SECRET_KEY=abc123"

[Install]
WantedBy=multi-user.target
```

### Explanation of Service File:

```bash
`ExecStart`: Points to the Gunicorn executable in your virtual environment and specifies to load the `app` object from `pbx_script_v3.py`.
`Restart=always`: Ensures the service restarts if it crashes.
`StandardOutput` / `StandardError`: Logs output to journalctl.
Save and close the file.
```

### 8. Enable and Start the Systemd Service
Now, instruct `systemd` to reload its configuration, enable your new service (so it starts on boot), and then start it immediately.

```bash
sudo systemctl daemon-reload           # Reload systemd configuration
sudo systemctl enable pbx_app.service  # Enable the service to start on boot
sudo systemctl start pbx_app.service   # Start the service immediately
```

### 9. Check Service Status and Logs
Verify that your service is running and monitor its output for any errors.

```bash
# Check the current status of the service
sudo systemctl status pbx_app.service

# View real-time logs from your application (press Ctrl+C to exit)
sudo journalctl -u pbx_app.service -f
```

You should see output indicating that Gunicorn has started and is listening on `127.0.0.1:5000`.

### 10. Configure Twilio Webhook (for testing)
For local testing, you'll need `ngrok` to expose your server to the internet. For production, you'd typically use a reverse proxy like Nginx or Apache.

1 - Start ngrok (in a separate terminal window):
```bash
ngrok http 5000
```
Copy the https:// "Forwarding" URL (e.g., `https://<RANDOM_ID>.ngrok-free.app`).

2 - Configure your Twilio Phone Number:
```bash
-Log in to your Twilio Console .
-Navigate to Phone Numbers > Manage > Active Numbers.
-Click on the phone number you want to use.
-Scroll to the Voice & Fax section.
-Under "A Call Comes In", set the dropdown to Webhook.
-In the text field, paste your `ngrok` URL, followed by `/incoming_call`.
---Example: `https://<YOUR_NGROK_URL>/incoming_call`
-Make sure the method is set to HTTP POST.
-Click Save.
```

### 11. Test Your PBX!

```bash
Call your Twilio phone number.
-You should hear the dynamic welcome message and the menu options based on your `EXTENSIONS` configuration.
-Try pressing the digits for `dial_external` extensions (e.g., `101`, `102`, `105`).
-Try pressing the digits for `voicemail` extensions (e.g., `103`, `105`).
---Leave a message.
---Check your server's `/opt/pbx_app/voicemails/` directory for the audio file.
---Check the configured recipient's email inbox for the voicemail.
-Try pressing the digits for `info_message` extensions (e.g., `104`).
```

### 12. Managing the Service

```bash
To stop: sudo systemctl stop pbx_app.service
To start: sudo systemctl start pbx_app.service
To restart (after code changes): sudo systemctl restart pbx_app.service
To disable (stop from starting on boot): sudo systemctl disable pbx_app.service
```
