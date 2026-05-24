import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_file_downloader import PacketDownloader

SCOPES = ["https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


def authenticate():
    """OAuth 2.0 desktop flow; reuses token.json when present."""
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def download_packets():
    drive = authenticate()
    pa_downloader = PacketDownloader(
        drive=drive,
        search_folder_id="15ef9UDdGImP6l5ZCDD7TdU6I6ycte-Xp",
        destination_dir="./downloads",
        custom_save_filename_pattern="req_{id}_doc",
    )

    pa_downloader.download_packet(id="208988")


if __name__ == "__main__":
    download_packets()