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
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Dial, Record, Hangup, Redirect

app = Flask(__name__)

# --- PBX Configuration ---
# Voicemail Storage
# Stores voicemails in a 'voicemails' folder in the app's current working directory.
# For systemd, if WorkingDirectory=/opt/pbx_app, this will be /opt/pbx_app/voicemails
VOICEMAIL_BASE_DIR = os.path.join(os.getcwd(), 'voicemails') 

# Email Configuration (IMPORTANT: Replace with your actual details)
# For Gmail, you'll need an "App password" if you have 2FA enabled.
# Go to Google Account -> Security -> App passwords.
SMTP_SERVER = 'smtp.gmail.com' # e.g., 'smtp.mail.yahoo.com', 'smtp.office365.com'
SMTP_PORT = 587 # Often 587 for TLS, or 465 for SSL
SMTP_USERNAME = 'your_sending_email@example.com' # Your email address
SMTP_PASSWORD = 'your_email_app_password' # Your email password or app password
SENDER_EMAIL = 'your_sending_email@example.com' # The email address that appears as the sender

# --- PBX Extension Configuration ---
EXTENSIONS = {
    '101': {
        'name': 'Sales Department',
        'type': 'dial_external',
        'target': '+15551234567' # IMPORTANT: Change to a real phone number for testing!
    },
    '102': {
        'name': 'Customer Support',
        'type': 'dial_external',
        'target': '+15559876543' # IMPORTANT: Change to a real phone number for testing!
    },
    '103': {
        'name': 'Leave a General Voicemail',
        'type': 'voicemail',
        'voicemail_dir_name': 'general', # This will create voicemails/general/
        'voicemail_recipient_email': 'general_voicemail_inbox@example.com' # IMPORTANT: Change to a real email address!
    },
    '104': {
        'name': 'General Information',
        'type': 'info_message',
        'message': 'Our business hours are Monday to Friday, 9 AM to 5 PM Eastern Time. For emergencies, please call back during business hours.'
    },
    '105': {
        'name': 'Billing Voicemail',
        'type': 'voicemail',
        'voicemail_dir_name': 'billing', # This will create voicemails/billing/
        'voicemail_recipient_email': 'billing_inbox@example.com' # IMPORTANT: Change to a real email address!
    },
    # Add more extensions here following the same format:
    # '200': {
    #     'name': 'Human Resources',
    #     'type': 'info_message',
    #     'message': 'For HR inquiries, please send an email to hr@example.com. Thank you.'
    # },
    # '201': {
    #     'name': 'IT Help Desk',
    #     'type': 'dial_external',
    #     'target': '+15556667777' # Replace with a real number
    # },
}

# Calculate the maximum number of digits an extension can have
MAX_EXT_DIGITS = max(len(ext) for ext in EXTENSIONS.keys())

# --- Helper Functions ---

def send_voicemail_email(recipient_email, caller_number, recording_url, local_file_path, ext_name):
    """Sends an email with the voicemail recording attached."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f"New Voicemail for {ext_name} from {caller_number}"

        body = f"""
        Hello,

        You have a new voicemail for the {ext_name} extension.
        
        Caller Number: {caller_number}
        Recording URL: {recording_url}

        The audio file is attached to this email.

        Best regards,
        Your PBX System
        """
        msg.attach(MIMEText(body, 'plain'))

        # Attach the audio file
        if os.path.exists(local_file_path):
            with open(local_file_path, 'rb') as attachment:
                # Twilio recordings are typically .wav or .mp3.
                # 'audio/wav' is a safe default, but adjust if always .mp3.
                part = MIMEBase('audio', 'wav') 
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(local_file_path)}"')
            msg.attach(part)
        else:
            print(f"ERROR: Voicemail file not found at {local_file_path} for email attachment.")

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls() # Secure the connection
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"Email sent successfully to {recipient_email} for {ext_name}.")
        return True
    except Exception as e:
        print(f"ERROR sending email to {recipient_email}: {e}")
        return False

# --- Flask Routes ---

@app.route("/incoming_call", methods=['GET', 'POST'])
def incoming_call():
    """Responds to incoming calls with a dynamic main menu IVR."""
    
    response = VoiceResponse()
    
    menu_options_text = "Welcome to our company's automated directory. "
    for ext, details in EXTENSIONS.items():
        menu_options_text += f"Press {ext} for {details['name']}. "
    
    with Gather(num_digits=MAX_EXT_DIGITS, action="/handle_extension_selection", method="POST", timeout=5) as gather:
        gather.say(menu_options_text)
    
    response.say("Sorry, we didn't receive your input. Please try again.")
    response.redirect("/incoming_call") 
    
    return Response(str(response), mimetype='text/xml')

@app.route("/handle_extension_selection", methods=['GET', 'POST'])
def handle_extension_selection():
    """Handles the caller's selected extension."""
    
    selected_ext = request.form.get('Digits')
    response = VoiceResponse()

    if selected_ext in EXTENSIONS:
        ext_details = EXTENSIONS[selected_ext]
        ext_type = ext_details['type']

        if ext_type == 'dial_external':
            response.say(f"Connecting you to the {ext_details['name']}. Please wait.")
            response.dial(ext_details['target'])
        elif ext_type == 'voicemail':
            response.say(f"You've selected {ext_details['name']}. Please leave your message after the tone. Press any key or hang up when you are finished.")
            # Pass the selected extension number to the handle_recording route
            response.record(max_length=30, action=f"/handle_recording/{selected_ext}", method="POST")
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
        response.say("Sorry, that was not a valid extension.")
        response.redirect("/incoming_call")
        
    return Response(str(response), mimetype='text/xml')

@app.route("/handle_recording/<selected_ext_num>", methods=['GET', 'POST'])
def handle_recording(selected_ext_num):
    """Handles the recorded voicemail, saves it, and sends an email."""
    
    recording_url = request.form.get('RecordingUrl')
    call_sid = request.form.get('CallSid')
    caller = request.form.get('From') # The caller's phone number

    print(f"\n--- NEW VOICEMAIL (Ext: {selected_ext_num}) ---")
    print(f"Call SID: {call_sid}")
    print(f"Caller: {caller}")
    print(f"Recording URL: {recording_url}")

    response = VoiceResponse()

    if not recording_url:
        print("ERROR: No recording URL received.")
        response.say("Sorry, there was an issue recording your message. Goodbye.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    ext_details = EXTENSIONS.get(selected_ext_num)
    if not ext_details or ext_details.get('type') != 'voicemail':
        print(f"ERROR: Invalid or non-voicemail extension {selected_ext_num} received for recording.")
        response.say("Sorry, there was an internal error with this voicemail option. Goodbye.")
        response.hangup()
        return Response(str(response), mimetype='text/xml')

    voicemail_dir_name = ext_details.get('voicemail_dir_name', 'unknown')
    recipient_email = ext_details.get('voicemail_recipient_email')
    ext_name = ext_details.get('name', f"Extension {selected_ext_num}")

    # 1. Create voicemail directories if they don't exist
    target_voicemail_dir = os.path.join(VOICEMAIL_BASE_DIR, voicemail_dir_name)
    os.makedirs(target_voicemail_dir, exist_ok=True)
    
    # 2. Define filename (using timestamp and Call SID for uniqueness)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    # Twilio recording URLs usually end in .wav or .mp3
    file_extension = recording_url.split('.')[-1] if '.' in recording_url else 'wav' # Default to wav
    voicemail_filename = f"{timestamp}_{caller.replace('+', '')}_{call_sid}.{file_extension}"
    local_file_path = os.path.join(target_voicemail_dir, voicemail_filename)

    # 3. Download the recording
    try:
        print(f"Downloading recording to {local_file_path}...")
        audio_content = requests.get(recording_url).content
        with open(local_file_path, 'wb') as f:
            f.write(audio_content)
        print("Recording downloaded successfully.")

        # 4. Send email notification
        if recipient_email:
            send_voicemail_email(recipient_email, caller, recording_url, local_file_path, ext_name)
        else:
            print(f"WARNING: No recipient email configured for extension {selected_ext_num}.")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to download recording from {recording_url}: {e}")
        response.say("We encountered an error downloading your message. Please try again later. Goodbye.")
    except Exception as e:
        print(f"An unexpected error occurred during voicemail handling: {e}")
        response.say("Sorry, an internal error occurred while processing your message. Goodbye.")
    
    response.say("Thank you for your message. Goodbye.")
    response.hangup()
    
    print(f"---------------------\n")
    return Response(str(response), mimetype='text/xml')

# IMPORTANT: Remove or comment out app.run() when using Gunicorn/Systemd for production
# For local testing without Gunicorn/Systemd, uncomment the lines below:
# if __name__ == "__main__":
#     os.makedirs(VOICEMAIL_BASE_DIR, exist_ok=True) # Ensure base voicemail dir exists for local testing
#     app.run(debug=True, port=5000)