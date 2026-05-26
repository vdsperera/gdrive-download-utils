from platform import system
import os
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_file_downloader import TemplatedFileDownloader
from google_file_downloader.exceptions import (
    DownloadError, ConfigurationError)

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
    try:
        drive = authenticate()
    except FileNotFoundError:
        print(f"Credentials file not found: {CREDENTIALS_FILE}")
        print("Download it from Google Cloud Console and place it in this directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Authentication failed: {e}")
        sys.exit(1)

    try:
        templated_downloader = TemplatedFileDownloader(
            drive=drive,
            search_folder_id="15ef9UDdGImP6l5ZCDD7TdU6I6ycte-Xp",
            destination_dir="./downloads",
            custom_save_filename_pattern="req_{id}_doc",
        )
    except ConfigurationError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    try:
        result = templated_downloader.download_packet(id="208988")
        for meta in result.downloaded:
            print(f"Downloaded: {meta.original_filename} -> {meta.local_path}")
        for path in result.skipped_duplicates:
            print(f"Skipped duplicate: {path}")
    except FileNotFoundError as e:
        print(f"Packet not found: {e}")
        sys.exit(1)
    except DownloadError as e:
        print(f"Download failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    download_packets()