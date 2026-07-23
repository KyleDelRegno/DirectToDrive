import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def get_credentials():
    creds = None

    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        except (json.JSONDecodeError, ValueError):
            os.remove("token.json")
            creds = None

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(
        host="localhost",
        port=8080,
        open_browser=True,
        authorization_prompt_message="Open this URL in your browser: {url}",
        success_message="Authentication complete. You may close this tab."
    )

    with open("token.json", "w") as token:
        token.write(creds.to_json())

    return creds