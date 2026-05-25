# google-file-downloader

A reusable Python utility for downloading files from authenticated Google Drive folders. Supports recursive folder traversal, filename search, file type filtering, duplicate handling, and automatic retries.

## Installation

```bash
pip install -e .
```

**Dependencies**

```bash
pip install -r requirements.txt
```

Requires Python 3.10+.

---

## Google Drive Authentication

This library requires OAuth 2.0 credentials. Set up via [Google Cloud Console](https://console.cloud.google.com/):

1. Create a project and enable the **Google Drive API**
2. Create OAuth 2.0 credentials (Desktop app) and download `credentials.json`
3. On first run, a browser window opens for authorization — a `token.json` is saved for subsequent runs

The `pa_download_demo.py` file shows a complete working auth flow.

---

## Usage

### `GoogleDriveFolderDownloader` — general purpose

The core class. Inject an authenticated Drive service and use it to search and download files from any folder.

```python
from pathlib import Path
from googleapiclient.discovery import build
from google_file_downloader import (
    GoogleDriveFolderDownloader,
    SearchOptions,
    SearchMatchMode,
    FileTypeFilter,
    TraversalOptions,
    DownloadOptions,
    DownloadMode,
    DuplicateFilenameStrategy,
)

drive = build("drive", "v3", credentials=creds)
downloader = GoogleDriveFolderDownloader(drive)

result = downloader.download_matching_files(
    folder_id="your_folder_id_here",
    search=SearchOptions(
        search_term="quarterly_report",
        match_mode=SearchMatchMode.PARTIAL,   # or EXACT
        case_sensitive=False,
    ),
    file_type=FileTypeFilter(extensions=frozenset({"pdf", "xlsx"})),
    traversal=TraversalOptions(recursive=True, max_depth=-1),
    download=DownloadOptions(
        destination_dir=Path("./downloads"),
        duplicate_strategy=DuplicateFilenameStrategy.RENAME,  # SKIP | OVERWRITE | FAIL
    ),
    download_mode=DownloadMode.ALL,   # or FIRST
)

print(f"Downloaded: {result.success_count}")
for meta in result.downloaded:
    print(f"  {meta.original_filename} -> {meta.local_path}")
for path in result.skipped_duplicates:
    print(f"  Skipped duplicate: {path}")
for err in result.errors:
    print(f"  Error: {err}")
```

#### Search-only (no download)

```python
matches = downloader.find_matching_files(
    folder_id="your_folder_id_here",
    search=SearchOptions(search_term="invoice"),
    file_type=FileTypeFilter(extensions=frozenset({"pdf"})),
)
for f in matches:
    print(f["name"], f["id"])
```

---

### `TemplatedFileDownloader` — templated/pattern-based wrapper

A higher-level class built on top of `GoogleDriveFolderDownloader`, tailored for downloading files matching a target pattern (e.g., `pa_{id}.pdf`) by ID.

```python
from google_file_downloader import TemplatedFileDownloader

downloader = TemplatedFileDownloader(
    drive=drive,
    search_folder_id="your_folder_id_here",
    destination_dir="./downloads",
    custom_save_filename_pattern="req_{id}_doc",
)

result = downloader.download_packet(id="208988")
```

This searches recursively for a file named exactly `pa_208988.pdf`, downloads all matches, and saves them as `req_208988_doc.pdf`. Raises `FileNotFoundError` if no matching file is found, or `DownloadError` if the download fails.

---

## Configuration Reference

### `SearchOptions`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search_term` | `str` | required | Filename to search for (extension ignored) |
| `match_mode` | `SearchMatchMode` | `PARTIAL` | `EXACT` or `PARTIAL` substring match |
| `case_sensitive` | `bool` | `False` | Case-sensitive matching |

### `FileTypeFilter`

| Parameter | Type | Description |
|---|---|---|
| `extensions` | `frozenset[str]` | Allowed extensions e.g. `{"pdf", "xlsx"}` |
| `mime_types` | `frozenset[str]` | Allowed MIME types e.g. `{"application/pdf"}` |

When both are set, a file matching either criterion is accepted.

### `TraversalOptions`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `recursive` | `bool` | `False` | Descend into subfolders |
| `max_depth` | `int` | `0` | `0` = root only, `1+` = N levels deep, `-1` = unlimited |

### `DownloadOptions`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `destination_dir` | `Path` | required | Local directory to save files |
| `custom_filename` | `str \| None` | `None` | Override saved filename (extension from original) |
| `duplicate_strategy` | `DuplicateFilenameStrategy` | `RENAME` | `RENAME`, `SKIP`, `OVERWRITE`, or `FAIL` |

### `DownloadMode`

| Value | Behaviour |
|---|---|
| `FIRST` | Download only the first matching file |
| `ALL` | Download every matching file |

---

## Error Handling

```python
from google_file_downloader.exceptions import (
    ConfigurationError,  # bad constructor arguments
    DownloadError,       # file download failed (includes retries)
    DriveApiError,       # Google Drive API call failed
)

try:
    result = downloader.download_packet(id="208988")
except FileNotFoundError as e:
    print(f"Packet not found: {e}")
except DownloadError as e:
    print(f"Download failed: {e}")
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

Download failures are retried automatically (3 attempts, exponential backoff: 2s, 4s). Only after all retries are exhausted is `DownloadError` raised.

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Project Structure

```
google_file_downloader/
├── downloader.py        # GoogleDriveFolderDownloader — core download logic
├── templated_downloader.py # TemplatedFileDownloader — templated/pattern-based wrapper
├── traversal.py         # Recursive Drive folder traversal
├── matcher.py           # Filename search and matching
├── file_type.py         # Extension and MIME type filtering
├── path_utils.py        # Local filesystem helpers
├── models.py            # Config dataclasses and result types
├── exceptions.py        # Custom exception hierarchy
└── mime.py              # MIME type mappings
```