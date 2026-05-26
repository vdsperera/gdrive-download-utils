"""
create_drive_structure.py
=========================
Creates a nested folder structure with unique blank PDFs locally,
then uploads everything to Google Drive.

Requirements:
    pip install reportlab google-api-python-client google-auth-httplib2 google-auth-oauthlib

Google Drive API setup (one-time):
    1. Go to https://console.cloud.google.com/
    2. Create a project → Enable "Google Drive API"
    3. Credentials → Create OAuth 2.0 Client ID (Desktop app)
    4. Download the JSON → save as  credentials.json  next to this script
    5. Run the script; a browser window will open to authorise access
       (token.json is saved for future runs)
"""

import os
import random
import io
from pathlib import Path

# ── PDF creation ────────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ── Google Drive API ─────────────────────────────────────────────────────────
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ── Configuration ─────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Set to None to create at Drive root, or paste a folder ID to put it inside:
#   e.g. PARENT_FOLDER_ID = "1A2B3C4D5E6F7G8H9I0J"
PARENT_FOLDER_ID = None

# Folder structure: { project: { month: [week_numbers] } }
STRUCTURE = {
    "P1": {"Jan": [1, 2, 3],       "Feb": [1, 2, 3, 4, 5], "Mar": [1, 2]},
    "P2": {"Jan": [1, 2, 3, 4, 5], "Feb": [1, 2],           "Mar": [1, 2, 3]},
    "P3": {"Jan": [1, 2],          "Feb": [1, 2, 3],         "Mar": [1, 2, 3, 4, 5]},
    "P4": {"Jan": [1, 2, 3, 4, 5], "Feb": [1, 2, 3],         "Mar": [1, 2]},
}

PDFS_PER_FOLDER_MIN = 2
PDFS_PER_FOLDER_MAX = 5

# ── Helpers ──────────────────────────────────────────────────────────────────

def authenticate() -> object:
    """Authenticate with Google and return a Drive service object."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


def make_drive_folder(service, name: str, parent_id: str | None) -> str:
    """Create a folder in Drive and return its ID."""
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    print(f"  📁 Created folder: {name}  (id={folder['id']})")
    return folder["id"]


def make_blank_pdf(filename: str) -> bytes:
    """Return bytes of a minimal single-page blank PDF labelled with filename."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    c.setFont("Helvetica", 14)
    c.drawCentredString(w / 2, h / 2, filename)
    c.save()
    return buf.getvalue()


def upload_pdf(service, filename: str, pdf_bytes: bytes, parent_id: str) -> None:
    """Upload a PDF file to a Drive folder."""
    meta = {"name": filename, "parents": [parent_id]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    service.files().create(body=meta, media_body=media, fields="id").execute()
    print(f"      📄 Uploaded: {filename}")


def generate_unique_names(count: int, used: set) -> list[str]:
    """Generate `count` unique pa_XXXXXX.pdf names not already in `used`."""
    names = []
    while len(names) < count:
        number = random.randint(100000, 999999)
        name = f"pa_{number}.pdf"
        if name not in used:
            used.add(name)
            names.append(name)
    return names


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("🔐 Authenticating with Google Drive…")
    service = authenticate()
    print("✅ Authenticated!\n")

    used_names: set[str] = set()   # globally unique PDF names

    for project, months in STRUCTURE.items():
        print(f"\n🗂  Project: {project}")
        proj_id = make_drive_folder(service, project, PARENT_FOLDER_ID)

        for month, weeks in months.items():
            print(f"  📅 Month: {month}")
            month_id = make_drive_folder(service, month, proj_id)

            for week in weeks:
                week_name = str(week)
                print(f"    📌 Week: {week_name}")
                week_id = make_drive_folder(service, week_name, month_id)

                # Random 2-5 unique PDFs per leaf folder
                count = random.randint(PDFS_PER_FOLDER_MIN, PDFS_PER_FOLDER_MAX)
                pdf_names = generate_unique_names(count, used_names)

                for pdf_name in pdf_names:
                    pdf_bytes = make_blank_pdf(pdf_name)
                    upload_pdf(service, pdf_name, pdf_bytes, week_id)

    print("\n🎉 Done! All folders and PDFs created in Google Drive.")


if __name__ == "__main__":
    main()