from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from google_file_downloader.downloader import GoogleDriveFolderDownloader
from google_file_downloader.models import (
    DownloadMode,
    DownloadOptions,
    DuplicateFilenameStrategy,
    FileTypeFilter,
    SearchMatchMode,
    SearchOptions,
    TraversalOptions,
)


def _file(id_: str, name: str, parent: str = "root", parent_name: str = "Root") -> dict:
    return {
        "id": id_,
        "name": name,
        "mimeType": "application/pdf",
        "parent_folder_id": parent,
        "parent_folder_name": parent_name,
    }


class FakeMediaDownload:
    def __init__(self, buffer, request) -> None:
        self._buffer = buffer

    def next_chunk(self):
        self._buffer.write(b"pdf-content")
        return None, True


@pytest.fixture
def drive_service() -> MagicMock:
    service = MagicMock()
    get_media = service.files.return_value.get_media
    get_media.return_value = MagicMock()
    return service


def test_find_matching_files_filters_by_name_and_type(drive_service: MagicMock):
    downloader = GoogleDriveFolderDownloader(drive_service)
    files = [
        _file("1", "Annual Report.pdf"),
        _file("2", "notes.txt", parent="root"),
    ]
    with patch(
        "google_file_downloader.downloader.iter_drive_files",
        return_value=iter(files),
    ):
        matches = downloader.find_matching_files(
            "root",
            SearchOptions(search_term="report", match_mode=SearchMatchMode.PARTIAL),
            file_type=FileTypeFilter(extensions=frozenset({"pdf"})),
        )
    assert len(matches) == 1
    assert matches[0]["name"] == "Annual Report.pdf"


def test_download_first_match_only(drive_service: MagicMock, tmp_path: Path):
    downloader = GoogleDriveFolderDownloader(drive_service)
    files = [
        _file("1", "Report A.pdf"),
        _file("2", "Report B.pdf"),
    ]

    with patch(
        "google_file_downloader.downloader.iter_drive_files",
        return_value=iter(files),
    ), patch(
        "google_file_downloader.downloader.MediaIoBaseDownload",
        FakeMediaDownload,
    ):
        result = downloader.download_matching_files(
            "root",
            SearchOptions(search_term="Report", match_mode=SearchMatchMode.PARTIAL),
            download=DownloadOptions(destination_dir=tmp_path),
            download_mode=DownloadMode.FIRST,
        )

    assert result.success_count == 1
    meta = result.downloaded[0]
    assert meta.original_filename == "Report A.pdf"
    assert meta.drive_file_id == "1"
    assert meta.local_path.exists()
    assert meta.local_path.read_bytes() == b"pdf-content"
    assert meta.parent_folder_id == "root"
    assert meta.mime_type == "application/pdf"


def test_download_all_with_custom_filename(drive_service: MagicMock, tmp_path: Path):
    downloader = GoogleDriveFolderDownloader(drive_service)
    files = [_file("1", "doc_a.pdf"), _file("2", "doc_b.pdf")]

    with patch(
        "google_file_downloader.downloader.iter_drive_files",
        return_value=iter(files),
    ), patch(
        "google_file_downloader.downloader.MediaIoBaseDownload",
        FakeMediaDownload,
    ):
        result = downloader.download_matching_files(
            "root",
            SearchOptions(search_term="doc", match_mode=SearchMatchMode.PARTIAL),
            download=DownloadOptions(
                destination_dir=tmp_path,
                custom_filename="bundle.pdf",
            ),
            download_mode=DownloadMode.ALL,
        )

    assert result.success_count == 2
    names = {m.downloaded_filename for m in result.downloaded}
    assert names == {"bundle_1.pdf", "bundle_2.pdf"}


def test_skip_duplicate_records_skipped(drive_service: MagicMock, tmp_path: Path):
    (tmp_path / "Report.pdf").write_bytes(b"existing")
    downloader = GoogleDriveFolderDownloader(drive_service)

    with patch(
        "google_file_downloader.downloader.iter_drive_files",
        return_value=iter([_file("1", "Report.pdf")]),
    ):
        result = downloader.download_matching_files(
            "root",
            SearchOptions(search_term="Report", match_mode=SearchMatchMode.EXACT),
            download=DownloadOptions(
                destination_dir=tmp_path,
                duplicate_strategy=DuplicateFilenameStrategy.SKIP,
            ),
        )

    assert result.success_count == 0
    assert len(result.skipped_duplicates) == 1


def test_traversal_options_validation():
    with pytest.raises(ValueError):
        TraversalOptions(recursive=False, max_depth=2)
    with pytest.raises(ValueError):
        TraversalOptions(recursive=False, max_depth=-1)
