# google-file-downloader

A reusable Python utility for downloading files from authenticated Google Drive folders. Supports recursive folder traversal, filename search, file type filtering, duplicate handling, and automatic retries.

Includes `GoogleDriveFolderDownloader` for general-purpose use and `TemplatedFileDownloader` for pattern-based downloads. Both support two interchangeable search strategies so you can tune API efficiency for your folder structure.

## Installation

**For local development**
```bash
poetry install
```

**For use in another project**
```bash
poetry add git+https://github.com/vdsperera/gdrive-download-utils.git
```

**Pin to a specific version (recommended for production)**
```bash
poetry add git+https://github.com/vdsperera/gdrive-download-utils.git@v1.0.0
```

Requires Python 3.10+.

---

## Google Drive Authentication

### Desktop / development (OAuth 2.0)

Set up via [Google Cloud Console](https://console.cloud.google.com/):

1. Create a project and enable the **Google Drive API**
2. Create OAuth 2.0 credentials (Desktop app) and download `credentials.json`
3. On first run, a browser window opens for authorization — a `token.json` is saved for subsequent runs

The `templated_download_demo.py` file shows a complete working auth flow.

### Automation / CI (Service Account — recommended)

For automation frameworks where no browser is available:

1. Create a service account in Google Cloud Console
2. Download the `service_account.json` key file
3. Share the target Drive folder with the service account email

```python
from google.oauth2 import service_account
from googleapiclient.discovery import build

credentials = service_account.Credentials.from_service_account_file(
    "service_account.json",
    scopes=["https://www.googleapis.com/auth/drive.readonly"],
)
drive = build("drive", "v3", credentials=credentials)
```

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
    SearchStrategy,
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
    strategy=SearchStrategy.SEARCH_FIRST,  # or TRAVERSAL — see below
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
    strategy=SearchStrategy.SEARCH_FIRST,
)
for f in matches:
    print(f["name"], f["id"])
```

---

### `TemplatedFileDownloader` — pattern-based wrapper

A higher-level class for downloading files that follow a naming pattern. Searches recursively by default, handles retries, and raises clearly on failure.

```python
from google_file_downloader import TemplatedFileDownloader, SearchStrategy

downloader = TemplatedFileDownloader(
    drive=drive,
    search_folder_id="your_folder_id_here",
    destination_dir="./downloads",
    custom_save_filename_pattern="req_{id}_doc",
    search_strategy=SearchStrategy.SEARCH_FIRST,  # optional — this is the default
)

result = downloader.download_packet(id="208988")
```

Default settings:

| Setting | Value |
|---|---|
| File name pattern | `pa_{id}` |
| File type | PDF only |
| Traversal | Recursive, unlimited depth |
| Duplicate strategy | Skip |
| Download mode | All matches |
| Match mode | Exact |
| Search strategy | `SEARCH_FIRST` |

Raises `FileNotFoundError` if no matching file is found, or `DownloadError` if the download fails.

#### Extending with a custom downloader

To create your own variant with different settings, subclass `TemplatedFileDownloader` and override only what changes:

```python
from google_file_downloader.templated_downloader import TemplatedFileDownloader
from google_file_downloader.models import FileTypeFilter, SearchStrategy

class InvoiceDownloader(TemplatedFileDownloader):
    def __init__(self, drive, search_folder_id, destination_dir, custom_save_filename_pattern):
        super().__init__(drive, search_folder_id, destination_dir, custom_save_filename_pattern)
        self.target_file_name_pattern = "inv_{id}"
        self.file_type = FileTypeFilter(extensions=frozenset({"xlsx"}))
        self.search_strategy = SearchStrategy.TRAVERSAL  # override if needed
```

---

## Search Strategies

Both `GoogleDriveFolderDownloader` and `TemplatedFileDownloader` support two interchangeable algorithms for locating files inside a Drive folder. Pass a `SearchStrategy` value to switch between them.

```python
from google_file_downloader import SearchStrategy
```

### `SearchStrategy.SEARCH_FIRST` *(default)*

Issues a single targeted `files.list` query to the Drive API using the filename as a filter, then walks each result's parent chain to confirm it lives inside the target folder.

**Best when:** the search term is selective and the folder tree is large. Typically requires only a handful of API calls regardless of tree depth.

### `SearchStrategy.TRAVERSAL`

Performs a recursive DFS walk of the folder tree — listing all children of every subfolder — and filters matches locally by filename.

**Best when:** you need to scan the full folder contents regardless of filename (e.g. auditing, bulk downloads), or when Drive's search index might be stale.

### Comparison

| | `SEARCH_FIRST` | `TRAVERSAL` |
|---|---|---|
| API calls | Low (proportional to matches) | High (proportional to folder count) |
| Speed | Fast for selective searches | Slower on large trees |
| Relies on Drive index | Yes | No |
| Deterministic order | No | Yes (DFS) |
| Results | Identical | Identical |

> Both strategies honour the same `TraversalOptions`, `FileTypeFilter`, and `SearchMatchMode` settings and produce the same results.

---

## Configuration Reference

### `SearchOptions`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search_term` | `str` | required | Filename to search for (extension ignored) |
| `match_mode` | `SearchMatchMode` | `PARTIAL` | `EXACT` or `PARTIAL` substring match |
| `case_sensitive` | `bool` | `False` | Case-sensitive matching |

### `SearchStrategy`

| Value | Algorithm |
|---|---|
| `SEARCH_FIRST` | Drive API query + ancestor verification *(default)* |
| `TRAVERSAL` | Recursive DFS folder walk, local filtering |

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
poetry install
poetry run pytest
```

---

## Project Structure

```
google_file_downloader/
├── downloader.py            # GoogleDriveFolderDownloader — core download logic
├── templated_downloader.py  # TemplatedFileDownloader — pattern-based wrapper
├── traversal.py             # DFS traversal + Search-First strategy implementations
├── matcher.py               # Filename search and matching
├── file_type.py             # Extension and MIME type filtering
├── path_utils.py            # Local filesystem helpers
├── models.py                # Config dataclasses, enums and result types
├── exceptions.py            # Custom exception hierarchy
└── mime.py                  # MIME type mappings
```