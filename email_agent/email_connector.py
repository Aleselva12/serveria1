import os
import re
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.message import EmailMessage
import base64

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')


def get_gmail_service():
    """Handles OAuth2 authentication and returns the API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def clean_email_body(text):
    """Cleans up messy email formatting, URLs, and marketing footers."""
    if not text:
        return ""

    # 1. Remove all long URLs and replace them with a clean tag
    text = re.sub(r'http[s]?://\S+', '[URL]', text)

    # 2. Remove weird unicode spacing characters
    text = text.replace('\xa0', ' ').replace('\u200b', '').replace('\u200a', ' ').replace('\r', '')

    # 3. Chop off common annoying footers to save space
    footers_to_cut = [
        "This email was intended for",
        "Unsubscribe:",
        "Build your network with InMail",
        "To learn more about us, please visit",
        "© 202"  # Catches copyright years like © 2024, © 2025, © 2026
    ]
    for footer in footers_to_cut:
        if footer in text:
            text = text.split(footer)[0]

    # 4. Clean up excessive line breaks and whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Turn multiple spaces into one
    text = re.sub(r'\n{3,}', '\n\n', text)  # Limit consecutive blank lines to 2

    return text.strip()


def extract_body(payload):
    """Drills through the payload to find the plain text body."""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif 'parts' in part:
                body = extract_body(part)
                if body:
                    return body
    elif payload.get('mimeType') == 'text/plain':
        data = payload['body'].get('data')
        if data:
            return base64.urlsafe_b64decode(data).decode('utf-8')
    return ""


def fetch_emails():
    """Fetches emails and returns them in the requested list of dictionaries."""
    service = get_gmail_service()

    # Fetch latest 10 messages
    results = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = results.get('messages', [])

    emails = []

    for msg in messages:
        msg_id = msg['id']
        full_msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        payload = full_msg.get('payload', {})
        headers = payload.get('headers', [])

        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), "Unknown")
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), "No Subject")

        raw_body = extract_body(payload)
        cleaned_body = clean_email_body(raw_body)

        email_dict = {
            "id": msg_id,
            "from": sender,
            "subject": subject,
            "body": cleaned_body
        }

        emails.append(email_dict)

    return emails


def save_as_draft(service, to_email, subject, body):
    """Takes AI-generated text and saves it as a draft in your Gmail."""

    # 1. Build the email
    message = EmailMessage()
    message.set_content(body)
    message['To'] = to_email
    message['From'] = 'me'
    message['Subject'] = subject

    # 2. Encode the email into the exact base64 format Google requires
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    # 3. Create the payload
    draft_payload = {
        'message': {
            'raw': encoded_message
        }
    }

    # 4. Push to Gmail
    try:
        draft = service.users().drafts().create(userId='me', body=draft_payload).execute()
        print(f"✅ Draft saved successfully! (ID: {draft['id']})")
        return draft
    except Exception as e:
        print(f"❌ Failed to create draft: {e}")
        return None