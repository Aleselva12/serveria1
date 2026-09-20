import base64
import os
import re
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.getenv("CORA_GMAIL_TOKEN_PATH", os.path.join(BASE_DIR, "token.json"))
CREDENTIALS_PATH = os.getenv(
    "CORA_GMAIL_CREDENTIALS_PATH",
    os.path.join(BASE_DIR, "credentials.json"),
)
MAX_EMAIL_BODY_CHARS = int(os.getenv("CORA_EMAIL_MAX_BODY_CHARS", "6000"))


def get_gmail_service():
    """Authenticate locally and return the Gmail API service."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    "Credenziali Gmail non trovate. Configura "
                    "CORA_GMAIL_CREDENTIALS_PATH."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH,
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        os.makedirs(os.path.dirname(TOKEN_PATH) or ".", exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def clean_email_body(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r"http[s]?://\S+", "[URL]", text)
    text = (
        text.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("\u200a", " ")
        .replace("\r", "")
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _decode_part(data: str) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def extract_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")

    if mime_type == "text/plain":
        return _decode_part(payload.get("body", {}).get("data", ""))

    for part in payload.get("parts", []):
        body = extract_body(part)
        if body:
            return body

    return ""


def _header(headers: list[dict], name: str, default: str = "") -> str:
    return next(
        (
            item.get("value", default)
            for item in headers
            if item.get("name", "").lower() == name.lower()
        ),
        default,
    )


def normalize_message(full_msg: dict) -> dict:
    payload = full_msg.get("payload", {})
    headers = payload.get("headers", [])
    raw_date = _header(headers, "Date")

    iso_date = None
    if raw_date:
        try:
            iso_date = parsedate_to_datetime(raw_date).isoformat()
        except Exception:
            iso_date = raw_date

    return {
        "id": full_msg.get("id"),
        "thread_id": full_msg.get("threadId"),
        "from": _header(headers, "From", "Unknown"),
        "to": _header(headers, "To", ""),
        "subject": _header(headers, "Subject", "No Subject"),
        "date": iso_date,
        "snippet": full_msg.get("snippet", ""),
        "body": clean_email_body(extract_body(payload))[:MAX_EMAIL_BODY_CHARS],
        "label_ids": full_msg.get("labelIds", []),
    }


def get_message(message_id: str) -> dict:
    """Fetch one Gmail message by its exact message ID."""
    if not message_id or not message_id.strip():
        raise ValueError("message_id mancante.")

    service = get_gmail_service()
    full_msg = service.users().messages().get(
        userId="me",
        id=message_id.strip(),
        format="full",
    ).execute()
    return normalize_message(full_msg)


def search_messages(query: str = "", max_results: int = 50) -> list[dict]:
    service = get_gmail_service()
    request = service.users().messages().list(
        userId="me",
        q=query or None,
        maxResults=max(1, min(max_results, 100)),
    )
    results = request.execute()

    emails = []
    for message in results.get("messages", []):
        emails.append(get_message(message["id"]))

    return emails


def messages_for_day(day: date, max_results: int = 100) -> list[dict]:
    next_day = day + timedelta(days=1)
    query = (
        f"after:{day.strftime('%Y/%m/%d')} "
        f"before:{next_day.strftime('%Y/%m/%d')}"
    )
    return search_messages(query=query, max_results=max_results)


def save_as_draft(to_email: str, subject: str, body: str) -> dict:
    service = get_gmail_service()

    message = EmailMessage()
    message.set_content(body)
    message["To"] = to_email
    message["From"] = "me"
    message["Subject"] = subject

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    return service.users().drafts().create(
        userId="me",
        body={"message": {"raw": encoded_message}},
    ).execute()
