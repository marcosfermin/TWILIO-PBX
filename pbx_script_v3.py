# pbx_script_v3.py | Author: Marcos Fermin (marcosdavid1794@gmail.com)
import os
import requests
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather

app = Flask(__name__)

# --- PBX Configuration ---
VOICEMAIL_BASE_DIR = os.path.join(os.getcwd(), 'voicemails')

# Email Configuration (replace these placeholders with your actual values)
SMTP_SERVER = 'mail.yourdomain.com'
SMTP_PORT = 465  # Use 465 for SSL or 587 for TLS
SMTP_USERNAME = 'your-email@yourdomain.com'
SMTP_PASSWORD = 'your-email-password'
SENDER_EMAIL = 'your-email@yourdomain.com'

EXTENSIONS = {
    '101': {
        'name': 'Contact the CEO',
        'type': 'dial_external',
        'target': '+12345678901'
    },
    '102': {
        'name': 'Contact the CIO',
        'type': 'dial_external',
        'target': '+12345678902'
    },
    '103': {
        'name': 'Leave a General Voicemail',
        'type': 'voicemail',
        'voicemail_dir_name': 'general',
        'voicemail_recipient_email': 'general-voicemail@yourdomain.com'
    },
    '104': {
        'name': 'General Information',
        'type': 'info_message',
        'message': 'Our business hours are Monday to Friday, 9 AM to 5 PM local time. For emergencies, please call back during business hours.'
    },
    '105': {
        'name': 'Billing Voicemail',
        'type': 'voicemail',
        'voicemail_dir_name': 'billing',
        'voicemail_recipient_email': 'billing@yourdomain.com'
    },
}

MAX_EXT_DIGITS = max(len(ext) for ext in EXTENSIONS.keys())

def get_external_ip():
    external_ip = request.headers.get('CF-Connecting-IP') or \
                  request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or \
                  request.remote_addr or 'Unknown IP'
    return external_ip

def send_voicemail_email(recipient_email, caller_number, recording_url, local_file_path, ext_name, caller_ip):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f"New Voicemail for {ext_name} from {caller_number}"

        body = f"""
Hello,

You have a new voicemail for the {ext_name} extension.

Caller Number: {caller_number}
Source IP: {caller_ip}
Recording URL: {recording_url}

The audio file is attached to this email.

Best regards,
Your PBX System
"""
        msg.attach(MIMEText(body, 'plain'))

        if os.path.exists(local_file_path):
            with open(local_file_path, 'rb') as attachment:
                part = MIMEBase('audio', 'wav')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(local_file_path)}"')
            msg.attach(part)
        else:
            print(f"ERROR: Voicemail file not found at {local_file_path} for email attachment.")

        if SMTP_PORT == 465:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)

        print(f"Email sent successfully to {recipient_email} for {ext_name}.")
        return True
    except Exception as e:
        print(f"ERROR sending email to {recipient_email}: {e}")
        return False

@app.route("/incoming_call", methods=['GET', 'POST'])
def incoming_call():
    caller_number = request.form.get('From', 'Unknown Caller')
    caller_ip = get_external_ip()
    print(f"Incoming call from {caller_number} (IP: {caller_ip}) to {request.form.get('To')}")

    response = VoiceResponse()
    menu_options_text = "Welcome to our company's automated directory. "
    for ext, details in EXTENSIONS.items():
        menu_options_text += f"Press {ext} for {details['name']}. "

    gather = Gather(num_digits=MAX_EXT_DIGITS, action="/handle_extension_selection", method="POST", timeout=5)
    gather.say(menu_options_text)
    response.append(gather)

    response.redirect("/handle_extension_selection")

    return Response(str(response), mimetype='text/xml')

@app.route("/handle_extension_selection", methods=['GET', 'POST'])
def handle_extension_selection():
    selected_ext = request.form.get('Digits')
    caller_number = request.form.get('From', 'Unknown Caller')
    caller_ip = get_external_ip()
    print(f"Selection '{selected_ext}' from {caller_number} (IP: {caller_ip})")

    response = VoiceResponse()

    if selected_ext in EXTENSIONS:
        ext_details = EXTENSIONS[selected_ext]
        ext_type = ext_details['type']

        if ext_type == 'dial_external':
            response.say(f"Connecting you to the {ext_details['name']}. Please wait.")
            response.dial(ext_details['target'])
        elif ext_type == 'voicemail':
            response.say(f"You've selected {ext_details['name']}. Please leave your message after the tone.")
            response.record(
                max_length=30,
                action=f"/handle_recording/{selected_ext}?caller_ip={caller_ip}",
                method="POST"
            )
            response.say("No message recorded. Goodbye.")
            response.hangup()
        elif ext_type == 'info_message':
            response.say(ext_details['message'])
            response.say("Thank you for calling. Goodbye.")
            response.hangup()
        else:
            response.say("Sorry, there was an internal error with your selection.")
            response.redirect("/incoming_call")
    else:
        response.say("Sorry, that was not a valid option.")
        response.redirect("/incoming_call")

    return Response(str(response), mimetype='text/xml')

@app.route("/handle_recording/<selected_ext_num>", methods=['GET', 'POST'])
def handle_recording(selected_ext_num):
    recording_url = request.form.get('RecordingUrl')
    call_sid = request.form.get('CallSid')
    caller = request.form.get('From', 'Unknown Caller')
    caller_ip = request.args.get('caller_ip', 'Unknown IP')

    print(f"\n--- NEW VOICEMAIL (Ext: {selected_ext_num}) ---")
    print(f"Call SID: {call_sid}")
    print(f"Caller: {caller}")
    print(f"Caller IP: {caller_ip}")
    print(f"Recording URL: {recording_url}")

    response = VoiceResponse()

    if not recording_url:
        print("ERROR: No recording URL received.")
        response.say("Sorry, there was an issue recording your message. Goodbye.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    ext_details = EXTENSIONS.get(selected_ext_num)
    if not ext_details or ext_details.get('type') != 'voicemail':
        print(f"ERROR: Invalid or non-voicemail extension {selected_ext_num}")
        response.say("Sorry, there was an internal error. Goodbye.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    voicemail_dir_name = ext_details.get('voicemail_dir_name', 'unknown')
    recipient_email = ext_details.get('voicemail_recipient_email')
    ext_name = ext_details.get('name', f"Extension {selected_ext_num}")

    target_dir = os.path.join(VOICEMAIL_BASE_DIR, voicemail_dir_name)
    os.makedirs(target_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = recording_url.split('.')[-1] if '.' in recording_url else 'wav'
    filename = f"{timestamp}_{caller.replace('+', '')}_{call_sid}.{ext}"
    local_path = os.path.join(target_dir, filename)

    try:
        print(f"Downloading to {local_path}...")
        audio = requests.get(recording_url).content
        with open(local_path, 'wb') as f:
            f.write(audio)
        print("Download complete.")

        if recipient_email:
            send_voicemail_email(recipient_email, caller, recording_url, local_path, ext_name, caller_ip)
        else:
            print(f"WARNING: No recipient email for extension {selected_ext_num}.")
    except requests.exceptions.RequestException as e:
        print(f"ERROR downloading recording: {e}")
        response.say("We encountered an error downloading your message. Goodbye.")
    except Exception as e:
        print(f"Unexpected error: {e}")
        response.say("An error occurred while processing your message. Goodbye.")

    response.say("Thank you for your message. Goodbye.")
    response.hangup()

    return Response(str(response), mimetype='text/xml')

# Uncomment below for local development
# if __name__ == "__main__":
#     os.makedirs(VOICEMAIL_BASE_DIR, exist_ok=True)
#     app.run(debug=True, port=5000)
