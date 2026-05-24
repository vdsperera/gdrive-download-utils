"""Google Drive authenticated folder file downloader."""

from __future__ import annotations

import io
import logging
from pathlib import Path
import tempfile
import shutil

from googleapiclient.http import MediaIoBaseDownload

from google_file_downloader.exceptions import DownloadError, DriveApiError
from google_file_downloader.file_type import file_matches_type
from google_file_downloader.matcher import filename_matches
from google_file_downloader.models import (
    DownloadMode,
    DownloadOptions,
    DownloadedFileMetadata,
    DownloadResult,
    DriveService,
    DuplicateFilenameStrategy,
    FileTypeFilter,
    SearchOptions,
    TraversalOptions,
)
from google_file_downloader.path_utils import resolve_target_path
from google_file_downloader.traversal import iter_drive_files

logger = logging.getLogger(__name__)


class GoogleDriveFolderDownloader:
    """
    Download files from an authenticated private Google Drive folder.

    Dependencies (Drive API client) are injected via the constructor so this
    utility stays decoupled from CLI, UI, or credential flows.

    Example::

        downloader = GoogleDriveFolderDownloader(drive_service)
        result = downloader.download_matching_files(
            folder_id="abc123",
            search=SearchOptions(search_term="report", match_mode=SearchMatchMode.PARTIAL),
            file_type=FileTypeFilter(extensions=frozenset({"pdf"})),
            traversal=TraversalOptions(recursive=True, max_depth=-1),
            download_mode=DownloadMode.FIRST,
            download=DownloadOptions(destination_dir=Path("./downloads")),
        )
    """

    def __init__(self, drive_service: DriveService) -> None:
        """
        Args:
            drive_service: Authenticated ``googleapiclient.discovery.Resource``
                for Drive API v3 (``build('drive', 'v3', credentials=...)``).
        """
        if drive_service is None:
            raise ValueError("drive_service must not be None")
        self._service = drive_service

    def find_matching_files(
        self,
        folder_id: str,
        search: SearchOptions,
        *,
        file_type: FileTypeFilter | None = None,
        traversal: TraversalOptions | None = None,
    ) -> list[dict]:
        """
        Search for files under ``folder_id`` without downloading.

        Returns raw Drive file metadata dicts enriched with parent folder fields.
        """
        traversal = traversal or TraversalOptions()
        matches: list[dict] = []

        for file_meta in iter_drive_files(self._service, folder_id, traversal):
            name = file_meta.get("name", "")
            mime = file_meta.get("mimeType")

            if not filename_matches(name, search):
                continue
            if not file_matches_type(name, mime, file_type):
                logger.debug("Skipping %s: file type filter", name)
                continue

            matches.append(file_meta)
            logger.info("Matched file: %s (id=%s)", name, file_meta.get("id"))

        return matches

    def download_matching_files(
        self,
        folder_id: str,
        search: SearchOptions,
        download: DownloadOptions,
        *,
        file_type: FileTypeFilter | None = None,
        traversal: TraversalOptions | None = None,
        download_mode: DownloadMode = DownloadMode.FIRST,
    ) -> DownloadResult:
        """
        Find and download files matching the search criteria.

        Args:
            folder_id: Google Drive folder ID.
            search: Filename search configuration.
            download: Destination directory, optional custom filename, duplicates.
            file_type: Optional extension/MIME filter.
            traversal: Folder recursion and depth limits.
            download_mode: Download first match only or all matches.

        Returns:
            ``DownloadResult`` with downloaded metadata, skips, and errors.
        """
        traversal = traversal or TraversalOptions()
        result = DownloadResult()

        try:
            matches = self.find_matching_files(
                folder_id,
                search,
                file_type=file_type,
                traversal=traversal,
            )
        except DriveApiError as exc:
            result.errors.append(str(exc))
            logger.exception("Drive API error while searching folder %s", folder_id)
            return result

        if not matches:
            logger.warning(
                "No files matched search_term=%r in folder %s",
                search.search_term,
                folder_id,
            )
            return result

        targets = matches[:1] if download_mode == DownloadMode.FIRST else matches

        for index, file_meta in enumerate(targets):
            try:
                metadata, skipped_path = self._download_single(
                    file_meta, download, index, len(targets)
                )
                if skipped_path is not None:
                    result.skipped_duplicates.append(str(skipped_path))
                elif metadata:
                    result.downloaded.append(metadata)
            except FileExistsError as exc:
                msg = str(exc)
                result.errors.append(msg)
                logger.error(msg)
            except DownloadError as exc:
                msg = str(exc)
                result.errors.append(msg)
                logger.exception("Download failed for %s", file_meta.get("id"))

        return result

    def _download_single(
        self,
        file_meta: dict,
        download: DownloadOptions,
        index: int,
        batch_size: int,
    ) -> tuple[DownloadedFileMetadata | None, Path | None]:
        file_id = file_meta["id"]
        original_name = file_meta.get("name", file_id)
        mime_type = file_meta.get("mimeType", "application/octet-stream")
        parent_id = file_meta.get("parent_folder_id", "")
        parent_name = file_meta.get("parent_folder_name")

        dest_name = self._resolve_download_filename(
            download, original_name, index, batch_size
        )

        try:
            target_path, should_download = resolve_target_path(
                download.destination_dir,
                dest_name,
                download.duplicate_strategy,
            )
        except FileExistsError:
            raise

        if not should_download:
            logger.info("Skipping duplicate: %s", target_path)
            return None, target_path

        logger.info("Downloading %s -> %s", original_name, target_path)
        self._write_file_to_disk(file_id, target_path)

        return (
            DownloadedFileMetadata(
                original_filename=original_name,
                downloaded_filename=target_path.name,
                local_path=target_path.resolve(),
                drive_file_id=file_id,
                mime_type=mime_type,
                parent_folder_id=parent_id,
                parent_folder_name=parent_name,
            ),
            None,
        )

    @staticmethod
    def _resolve_download_filename(
        download: DownloadOptions,
        original_name: str,
        index: int,
        batch_size: int,
    ) -> str:
        if download.custom_filename:
            custom_path = Path(download.custom_filename)
            custom_stem = custom_path.stem or "download"
            
            original_path = Path(original_name)
            original_suffix = original_path.suffix
            
            if batch_size > 1:
                return f"{custom_stem}_{index + 1}{original_suffix}"
            return f"{custom_stem}{original_suffix}"
        return original_name

    def _write_file_to_disk(self, file_id: str, target_path: Path) -> None:
        try:
            request = self._service.files().get_media(fileId=file_id)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            # buffer = io.BytesIO()
            # downloader = MediaIoBaseDownload(buffer, request)
            # done = False
            # while not done:
            #     _, done = downloader.next_chunk()

            
            # target_path.write_bytes(buffer.getvalue())

            with tempfile.NamedTemporaryFile(
                delete=False,
                dir=target_path.parent,  # same dir = atomic move guaranteed
                suffix=".tmp"
            ) as tmp:
                tmp_path = Path(tmp.name)
                downloader = MediaIoBaseDownload(tmp, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()

            tmp_path.rename(target_path)  # atomic on same filesystem
        except Exception as exc:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()  # clean up partial file
            raise DownloadError(
                f"Failed to download file {file_id}",
                file_id=file_id,
                cause=exc,
            ) from exc
