"""Configuration and result models for Google Drive file downloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SearchMatchMode(str, Enum):
    """How search terms are matched against Drive file names."""

    EXACT = "exact"
    PARTIAL = "partial"


class DownloadMode(str, Enum):
    """Whether to download the first match or every match."""

    FIRST = "first"
    ALL = "all"


class DuplicateFilenameStrategy(str, Enum):
    """How to handle filename collisions in the destination directory."""

    FAIL = "fail"
    SKIP = "skip"
    OVERWRITE = "overwrite"
    RENAME = "rename"


@dataclass(frozen=True)
class SearchOptions:
    """Filename search configuration."""

    search_term: str
    match_mode: SearchMatchMode = SearchMatchMode.PARTIAL
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        if not self.search_term.strip():
            raise ValueError("search_term must not be empty")


@dataclass(frozen=True)
class FileTypeFilter:
    """
    Restrict matches by file extension and/or MIME type.

    At least one of ``extensions`` or ``mime_types`` should be set when filtering
    is required. When both are set, a file must satisfy at least one criterion
    (extension OR MIME type).
    """

    extensions: frozenset[str] = field(default_factory=frozenset)
    mime_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        normalized_ext = frozenset(
            ext.lower().lstrip(".") for ext in self.extensions if ext
        )
        normalized_mime = frozenset(m for m in self.mime_types if m)
        object.__setattr__(self, "extensions", normalized_ext)
        object.__setattr__(self, "mime_types", normalized_mime)

    @property
    def is_active(self) -> bool:
        return bool(self.extensions or self.mime_types)


@dataclass(frozen=True)
class TraversalOptions:
    """
    Folder traversal configuration.

    ``max_depth``:
      - ``0``: only the root folder (no subfolders)
      - ``1+``: descend into subfolders up to that depth
      - ``-1``: unlimited depth (requires ``recursive=True``)
    """

    recursive: bool = False
    max_depth: int = 0

    def __post_init__(self) -> None:
        if self.max_depth < -1:
            raise ValueError("max_depth must be >= -1")
        if self.max_depth == -1 and not self.recursive:
            raise ValueError("max_depth=-1 requires recursive=True")
        if self.max_depth > 0 and not self.recursive:
            raise ValueError("max_depth > 0 requires recursive=True")


@dataclass(frozen=True)
class DownloadOptions:
    """Destination path and duplicate-handling behavior."""

    destination_dir: Path
    custom_filename: str | None = None
    duplicate_strategy: DuplicateFilenameStrategy = DuplicateFilenameStrategy.RENAME

    def __post_init__(self) -> None:
        if not self.custom_filename and self.duplicate_strategy == DuplicateFilenameStrategy.FAIL:
            pass
        if self.custom_filename and not self.custom_filename.strip():
            raise ValueError("custom_filename must not be blank when provided")


@dataclass(frozen=True)
class DownloadedFileMetadata:
    """Structured metadata for a successfully downloaded file."""

    original_filename: str
    downloaded_filename: str
    local_path: Path
    drive_file_id: str
    mime_type: str
    parent_folder_id: str
    parent_folder_name: str | None = None


@dataclass
class DownloadResult:
    """Outcome of a download operation."""

    downloaded: list[DownloadedFileMetadata] = field(default_factory=list)
    skipped_duplicates: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.downloaded)


# googleapiclient.discovery.Resource — kept loose for testability
DriveService = Any
