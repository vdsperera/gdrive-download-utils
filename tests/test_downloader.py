from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from google_file_downloader.downloader import GoogleDriveFolderDownloader
from google_file_downloader.exceptions import DownloadError, DriveApiError
from google_file_downloader.models import (
    DownloadMode,
    DownloadOptions,
    DuplicateFilenameStrategy,
    FileTypeFilter,
    SearchMatchMode,
    SearchOptions,
    SearchStrategy,
    TraversalOptions,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file(id_: str, name: str, parent: str = "root", parent_name: str = "Root",
          mime: str = "application/pdf") -> dict:
    return {
        "id": id_,
        "name": name,
        "mimeType": mime,
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
    service.files.return_value.get_media.return_value = MagicMock()
    return service


def _downloader(service=None):
    return GoogleDriveFolderDownloader(service or MagicMock())


def _default_opts(tmp_path, strategy=DuplicateFilenameStrategy.RENAME):
    return DownloadOptions(destination_dir=tmp_path, duplicate_strategy=strategy)


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_none_service_raises(self):
        with pytest.raises(ValueError):
            GoogleDriveFolderDownloader(None)

    def test_valid_service_accepted(self):
        assert _downloader() is not None


# ---------------------------------------------------------------------------
# find_matching_files
# ---------------------------------------------------------------------------

class TestFindMatchingFiles:
    def test_filters_by_name_and_type(self, drive_service):
        # Existing test kept intact
        downloader = GoogleDriveFolderDownloader(drive_service)
        files = [_file("1", "Annual Report.pdf"), _file("2", "notes.txt")]
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter(files)):
            matches = downloader.find_matching_files(
                "root",
                SearchOptions(search_term="report", match_mode=SearchMatchMode.PARTIAL),
                file_type=FileTypeFilter(extensions=frozenset({"pdf"})),
            )
        assert len(matches) == 1
        assert matches[0]["name"] == "Annual Report.pdf"

    def test_returns_empty_when_no_match(self, drive_service):
        downloader = GoogleDriveFolderDownloader(drive_service)
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter([])):
            result = downloader.find_matching_files("root", SearchOptions(search_term="report"))
        assert result == []

    def test_drive_api_error_propagates(self):
        service = MagicMock()
        service.files().list().execute.side_effect = Exception("API error")
        d = GoogleDriveFolderDownloader(service)
        with pytest.raises(DriveApiError):
            d.find_matching_files("root", SearchOptions(search_term="report"))


# ---------------------------------------------------------------------------
# download_matching_files
# ---------------------------------------------------------------------------

class TestDownloadMatchingFiles:
    def test_download_first_match_only(self, drive_service, tmp_path):
        # Existing test kept intact
        downloader = GoogleDriveFolderDownloader(drive_service)
        files = [_file("1", "Report A.pdf"), _file("2", "Report B.pdf")]
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter(files)), \
             patch("google_file_downloader.downloader.MediaIoBaseDownload", FakeMediaDownload):
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

    def test_download_all_with_custom_filename(self, drive_service, tmp_path):
        # Existing test kept intact
        downloader = GoogleDriveFolderDownloader(drive_service)
        files = [_file("1", "doc_a.pdf"), _file("2", "doc_b.pdf")]
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter(files)), \
             patch("google_file_downloader.downloader.MediaIoBaseDownload", FakeMediaDownload):
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="doc", match_mode=SearchMatchMode.PARTIAL),
                download=DownloadOptions(destination_dir=tmp_path, custom_filename="bundle.pdf"),
                download_mode=DownloadMode.ALL,
            )
        assert result.success_count == 2
        assert {m.downloaded_filename for m in result.downloaded} == {"bundle_1.pdf", "bundle_2.pdf"}

    def test_custom_filename_retains_original_extension(self, drive_service, tmp_path):
        # Existing test kept intact
        downloader = GoogleDriveFolderDownloader(drive_service)
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter([_file("1", "doc_a.xlsx")])), \
             patch("google_file_downloader.downloader.MediaIoBaseDownload", FakeMediaDownload):
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="doc", match_mode=SearchMatchMode.PARTIAL),
                download=DownloadOptions(destination_dir=tmp_path, custom_filename="my_custom_name.pdf"),
                download_mode=DownloadMode.FIRST,
            )
        assert result.downloaded[0].downloaded_filename == "my_custom_name.xlsx"

    def test_skip_duplicate_records_skipped(self, drive_service, tmp_path):
        # Existing test kept intact
        (tmp_path / "Report.pdf").write_bytes(b"existing")
        downloader = GoogleDriveFolderDownloader(drive_service)
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter([_file("1", "Report.pdf")])):
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="Report", match_mode=SearchMatchMode.EXACT),
                download=DownloadOptions(destination_dir=tmp_path, duplicate_strategy=DuplicateFilenameStrategy.SKIP),
            )
        assert result.success_count == 0
        assert len(result.skipped_duplicates) == 1

    def test_no_matches_returns_empty_result(self, drive_service, tmp_path):
        downloader = GoogleDriveFolderDownloader(drive_service)
        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter([])):
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="report"),
                download=_default_opts(tmp_path),
            )
        assert result.downloaded == []
        assert result.errors == []
        assert result.skipped_duplicates == []

    def test_drive_api_error_captured_in_result(self, tmp_path):
        service = MagicMock()
        service.files().list().execute.side_effect = Exception("API down")
        d = GoogleDriveFolderDownloader(service)
        result = d.download_matching_files(
            "root", SearchOptions(search_term="report"), download=_default_opts(tmp_path)
        )
        assert len(result.errors) == 1
        assert result.downloaded == []

    def test_fail_duplicate_adds_to_errors(self, drive_service, tmp_path):
        (tmp_path / "report.pdf").write_bytes(b"existing")
        downloader = GoogleDriveFolderDownloader(drive_service)
        with patch("google_file_downloader.downloader.iter_drive_files", return_value=iter([_file("1", "report.pdf")])):
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="report"),
                download=_default_opts(tmp_path, DuplicateFilenameStrategy.FAIL),
                strategy=SearchStrategy.TRAVERSAL,
            )
        assert len(result.errors) == 1
        assert result.downloaded == []

    def test_download_error_per_file_continues_remaining(self, drive_service, tmp_path):
        downloader = GoogleDriveFolderDownloader(drive_service)
        files = [_file("f1", "report_a.pdf"), _file("f2", "report_b.pdf")]
        call_n = {"n": 0}

        def failing_first(file_id, target_path, **kwargs):
            call_n["n"] += 1
            if call_n["n"] == 1:
                raise DownloadError("timeout", file_id=file_id)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(b"ok")

        with patch("google_file_downloader.downloader.iter_drive_files_strategy_a", return_value=iter(files)):
            downloader._write_file_to_disk = failing_first
            result = downloader.download_matching_files(
                "root",
                SearchOptions(search_term="report"),
                download=_default_opts(tmp_path),
                download_mode=DownloadMode.ALL,
            )
        assert len(result.errors) == 1
        assert len(result.downloaded) == 1


# ---------------------------------------------------------------------------
# _resolve_download_filename
# ---------------------------------------------------------------------------

class TestResolveDownloadFilename:
    def _opts(self, custom=None):
        o = MagicMock()
        o.custom_filename = custom
        return o

    def test_no_custom_uses_original(self):
        result = GoogleDriveFolderDownloader._resolve_download_filename(
            self._opts(None), "report.pdf", 0, 1
        )
        assert result == "report.pdf"

    def test_custom_single_file_uses_stem_with_original_ext(self):
        assert GoogleDriveFolderDownloader._resolve_download_filename(
            self._opts("my_doc"), "report.pdf", 0, 1
        ) == "my_doc.pdf"

    def test_custom_batch_appends_1_indexed_counter(self):
        opts = self._opts("my_doc")
        assert GoogleDriveFolderDownloader._resolve_download_filename(opts, "a.pdf", 0, 3) == "my_doc_1.pdf"
        assert GoogleDriveFolderDownloader._resolve_download_filename(opts, "b.pdf", 1, 3) == "my_doc_2.pdf"
        assert GoogleDriveFolderDownloader._resolve_download_filename(opts, "c.pdf", 2, 3) == "my_doc_3.pdf"

    def test_custom_ext_ignored_original_used(self):
        assert GoogleDriveFolderDownloader._resolve_download_filename(
            self._opts("my_doc.txt"), "report.pdf", 0, 1
        ) == "my_doc.pdf"

    def test_original_has_no_extension(self):
        assert GoogleDriveFolderDownloader._resolve_download_filename(
            self._opts("my_doc"), "report", 0, 1
        ) == "my_doc"


# ---------------------------------------------------------------------------
# _write_file_to_disk
# ---------------------------------------------------------------------------

class TestWriteFileToDisk:
    def test_raises_download_error_on_failure(self, drive_service, tmp_path):
        drive_service.files().get_media.side_effect = Exception("Connection reset")
        d = GoogleDriveFolderDownloader(drive_service)
        with pytest.raises(DownloadError) as exc_info:
            d._write_file_to_disk("myfileid", tmp_path / "out.pdf", retries=1)
        assert exc_info.value.file_id == "myfileid"

    def test_no_partial_file_at_target_on_failure(self, drive_service, tmp_path):
        drive_service.files().get_media.side_effect = Exception("timeout")
        d = GoogleDriveFolderDownloader(drive_service)
        target = tmp_path / "report.pdf"
        with pytest.raises(DownloadError):
            d._write_file_to_disk("f1", target, retries=1)
        assert not target.exists()

    def test_no_tmp_file_left_on_failure(self, drive_service, tmp_path):
        drive_service.files().get_media.side_effect = Exception("timeout")
        d = GoogleDriveFolderDownloader(drive_service)
        with pytest.raises(DownloadError):
            d._write_file_to_disk("f1", tmp_path / "report.pdf", retries=1)
        assert list(tmp_path.glob("*.tmp")) == []

    def test_successful_write_correct_content(self, drive_service, tmp_path):
        target = tmp_path / "report.pdf"
        with patch("google_file_downloader.downloader.MediaIoBaseDownload", FakeMediaDownload):
            GoogleDriveFolderDownloader(drive_service)._write_file_to_disk("f1", target)
        assert target.read_bytes() == b"pdf-content"

    def test_parent_directories_created(self, drive_service, tmp_path):
        nested = tmp_path / "a" / "b" / "report.pdf"
        with patch("google_file_downloader.downloader.MediaIoBaseDownload", FakeMediaDownload):
            GoogleDriveFolderDownloader(drive_service)._write_file_to_disk("f1", nested)
        assert nested.exists()

    def test_retries_on_transient_failure_then_succeeds(self, drive_service, tmp_path):
        target = tmp_path / "report.pdf"
        call_n = {"n": 0}

        class FailOnceThenSucceed:
            def __init__(self, buf, req):
                self._buf = buf
            def next_chunk(self):
                call_n["n"] += 1
                if call_n["n"] == 1:
                    raise IOError("transient error")
                self._buf.write(b"pdf-content")
                return None, True

        with patch("google_file_downloader.downloader.MediaIoBaseDownload", FailOnceThenSucceed), \
             patch("google_file_downloader.downloader.time.sleep"):
            GoogleDriveFolderDownloader(drive_service)._write_file_to_disk("f1", target, retries=3)

        assert target.read_bytes() == b"pdf-content"

    def test_exhausts_all_retries_then_raises(self, drive_service, tmp_path):
        attempt_count = {"n": 0}
        def counting(*args, **kwargs):
            attempt_count["n"] += 1
            raise Exception("persistent failure")
        drive_service.files().get_media.side_effect = counting

        with patch("google_file_downloader.downloader.time.sleep"):
            with pytest.raises(DownloadError):
                GoogleDriveFolderDownloader(drive_service)._write_file_to_disk(
                    "f1", tmp_path / "report.pdf", retries=3
                )
        assert attempt_count["n"] == 3

    def test_no_sleep_after_final_attempt(self, drive_service, tmp_path):
        drive_service.files().get_media.side_effect = Exception("fail")
        with patch("google_file_downloader.downloader.time.sleep") as mock_sleep:
            with pytest.raises(DownloadError):
                GoogleDriveFolderDownloader(drive_service)._write_file_to_disk(
                    "f1", tmp_path / "report.pdf", retries=3
                )
        assert mock_sleep.call_count == 2  # between attempt 1→2 and 2→3, not after 3

    def test_backoff_doubles_each_attempt(self, drive_service, tmp_path):
        drive_service.files().get_media.side_effect = Exception("fail")
        with patch("google_file_downloader.downloader.time.sleep") as mock_sleep:
            with pytest.raises(DownloadError):
                GoogleDriveFolderDownloader(drive_service)._write_file_to_disk(
                    "f1", tmp_path / "report.pdf", retries=3, backoff_base=2.0
                )
        assert [c.args[0] for c in mock_sleep.call_args_list] == [2.0, 4.0]


# ---------------------------------------------------------------------------
# TraversalOptions validation (kept from original location)
# ---------------------------------------------------------------------------

def test_traversal_options_validation():
    with pytest.raises(ValueError):
        TraversalOptions(recursive=False, max_depth=2)
    with pytest.raises(ValueError):
        TraversalOptions(recursive=False, max_depth=-1)