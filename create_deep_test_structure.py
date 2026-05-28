"""
create_deep_test_structure.py
==============================
Creates a realistic, deeply-nested folder structure in Google Drive
for testing the google-file-downloader traversal logic.

Structure (up to 6 levels deep):
  TestRoot_<timestamp>/
  ├── Division_A/
  │   ├── Department_Finance/
  │   │   ├── Year_2024/
  │   │   │   ├── Q1/
  │   │   │   │   ├── January/   ← leaf: PDFs
  │   │   │   │   ├── February/  ← leaf: PDFs
  │   │   │   │   └── March/     ← leaf: PDFs
  │   │   │   ├── Q2/ ...
  │   │   │   ├── Q3/ ...
  │   │   │   └── Q4/ ...
  │   │   └── Year_2025/ ...
  │   └── Department_HR/ ...
  ├── Division_B/ ...
  └── Division_C/ ...

Total depth: 6 levels  (Root → Division → Department → Year → Quarter → Month)
Files:       2–4 PDFs per leaf folder  (~pa_XXXXXX.pdf naming convention)

Usage:
    python create_deep_test_structure.py
    python create_deep_test_structure.py --parent-id <FOLDER_ID>  # put inside existing folder
    python create_deep_test_structure.py --dry-run               # print tree, don't upload
"""

import argparse
import io
import os
import random
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ── Auth ──────────────────────────────────────────────────────────────────────

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
        with open(TOKEN_FILE, "w") as fh:
            fh.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ── Drive helpers ─────────────────────────────────────────────────────────────

def make_drive_folder(service, name: str, parent_id: str | None, depth: int) -> str:
    """Create a Drive folder and return its ID."""
    indent = "  " * depth
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    folder = service.files().create(body=meta, fields="id").execute()
    print(f"{indent}📁 {name}  (id={folder['id']})")
    return folder["id"]


def make_pdf_bytes(label: str) -> bytes:
    """Return bytes of a single-page PDF labelled with `label`."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, h / 2 + 20, label)
    c.setFont("Helvetica", 11)
    c.drawCentredString(w / 2, h / 2 - 10, "Test file — google-file-downloader")
    c.save()
    return buf.getvalue()


def upload_pdf(service, filename: str, pdf_bytes: bytes, parent_id: str, depth: int) -> None:
    indent = "  " * depth
    meta = {"name": filename, "parents": [parent_id]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    result = service.files().create(body=meta, media_body=media, fields="id").execute()
    print(f"{indent}📄 {filename}  (id={result['id']})")


# ── Unique name generator ─────────────────────────────────────────────────────

_used_names: set[str] = set()


def unique_pdf_names(count: int) -> list[str]:
    names = []
    while len(names) < count:
        n = f"pa_{random.randint(100_000, 999_999)}.pdf"
        if n not in _used_names:
            _used_names.add(n)
            names.append(n)
    return names


# ── Folder structure definition ───────────────────────────────────────────────

DIVISIONS = ["Division_A", "Division_B", "Division_C"]

DEPARTMENTS = {
    "Division_A": ["Dept_Finance", "Dept_Operations"],
    "Division_B": ["Dept_HR", "Dept_Legal", "Dept_IT"],
    "Division_C": ["Dept_Marketing", "Dept_Sales"],
}

YEARS = ["Year_2023", "Year_2024", "Year_2025"]

QUARTERS = {
    "Q1": ["January", "February", "March"],
    "Q2": ["April", "May", "June"],
    "Q3": ["July", "August", "September"],
    "Q4": ["October", "November", "December"],
}

PDFS_MIN = 2
PDFS_MAX = 4


# ── Builder (real) ────────────────────────────────────────────────────────────

def build_structure(service, root_id: str) -> dict:
    """
    Build the full 6-level structure under `root_id`.
    Returns a summary dict: { 'folders': int, 'files': int }
    """
    stats = {"folders": 0, "files": 0}

    for div in DIVISIONS:
        div_id = make_drive_folder(service, div, root_id, depth=1)
        stats["folders"] += 1

        for dept in DEPARTMENTS[div]:
            dept_id = make_drive_folder(service, dept, div_id, depth=2)
            stats["folders"] += 1

            for year in YEARS:
                year_id = make_drive_folder(service, year, dept_id, depth=3)
                stats["folders"] += 1

                for quarter, months in QUARTERS.items():
                    q_id = make_drive_folder(service, quarter, year_id, depth=4)
                    stats["folders"] += 1

                    for month in months:
                        m_id = make_drive_folder(service, month, q_id, depth=5)
                        stats["folders"] += 1

                        for pdf_name in unique_pdf_names(random.randint(PDFS_MIN, PDFS_MAX)):
                            pdf_bytes = make_pdf_bytes(pdf_name)
                            upload_pdf(service, pdf_name, pdf_bytes, m_id, depth=6)
                            stats["files"] += 1

    return stats


# ── Dry-run (no upload) ───────────────────────────────────────────────────────

def dry_run():
    """Print the full tree that would be created, without touching Drive."""
    root_name = f"TestRoot_{int(time.time())}"
    print(f"\n[DRY RUN] Would create root: {root_name}\n")
    folders = files = 0

    for div in DIVISIONS:
        print(f"  📁 {div}")
        folders += 1
        for dept in DEPARTMENTS[div]:
            print(f"    📁 {dept}")
            folders += 1
            for year in YEARS:
                print(f"      📁 {year}")
                folders += 1
                for quarter, months in QUARTERS.items():
                    print(f"        📁 {quarter}")
                    folders += 1
                    for month in months:
                        count = random.randint(PDFS_MIN, PDFS_MAX)
                        print(f"          📁 {month}  [{count} PDFs]")
                        folders += 1
                        files += count

    print(f"\n[DRY RUN] Summary: {folders} folders, ~{files} PDFs")
    print("[DRY RUN] Re-run without --dry-run to actually create this in Drive.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Create a deep test folder structure in Google Drive."
    )
    parser.add_argument(
        "--parent-id",
        default=None,
        metavar="FOLDER_ID",
        help="Drive folder ID to create the root inside (default: Drive root).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the tree that would be created without uploading anything.",
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    print("🔐 Authenticating with Google Drive…")
    try:
        service = authenticate()
    except FileNotFoundError:
        print(f"❌ {CREDENTIALS_FILE} not found. Download it from Google Cloud Console.")
        sys.exit(1)
    print("✅ Authenticated!\n")

    root_name = f"TestRoot_{int(time.time())}"
    print(f"🌳 Creating root folder: {root_name}")
    root_id = make_drive_folder(service, root_name, args.parent_id, depth=0)
    print(f"\n📂 Root folder ID: {root_id}")
    print("   (Copy this ID — you can use it as search_folder_id in your downloader)\n")

    print("⏳ Building structure (6 levels deep)…\n")
    stats = build_structure(service, root_id)

    print(f"\n🎉 Done!")
    print(f"   Root folder ID : {root_id}")
    print(f"   Folders created: {stats['folders']}")
    print(f"   Files uploaded : {stats['files']}")
    print(f"\n   Drive link: https://drive.google.com/drive/folders/{root_id}")


if __name__ == "__main__":
    main()
