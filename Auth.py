import os
import sys
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def get_app_support_dir():
    base = Path.home() / "Library" / "Application Support" / "DriveToSSD"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_token_path():
    return get_app_support_dir() / "token.json"

def get_credentials_path():
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parent
    return base / "credentials.json"

def get_credentials():
    creds = None
    token_path = get_token_path()
    credentials_path = get_credentials_path()

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except (json.JSONDecodeError, ValueError):
            token_path.unlink(missing_ok=True)
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    creds = flow.run_local_server(
        host="localhost",
        port=8080,
        open_browser=True,
        authorization_prompt_message="Open this URL in your browser: {url}",
        success_message="Authentication complete. You may close this tab."
    )

    token_path.write_text(creds.to_json())
    return creds