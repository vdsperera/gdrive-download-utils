from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from google_file_downloader import (
    DownloadResult,
    DownloadedFileMetadata,
    TemplatedFileDownloader,
)
from google_file_downloader.exceptions import ConfigurationError, DownloadError
from google_file_downloader.models import (
    DownloadMode,
    DuplicateFilenameStrategy,
    SearchMatchMode,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_drive() -> MagicMock:
    return MagicMock()


@pytest.fixture
def tfd(mock_drive, tmp_path) -> TemplatedFileDownloader:
    return TemplatedFileDownloader(
        drive=mock_drive,
        search_folder_id="folder_abc",
        destination_dir=str(tmp_path),
        custom_save_filename_pattern="req_{id}_doc",
    )


def _success_result(tmp_path: Path, packet_id: str = "123") -> DownloadResult:
    return DownloadResult(
        downloaded=[
            DownloadedFileMetadata(
                original_filename=f"pa_{packet_id}.pdf",
                downloaded_filename=f"req_{packet_id}_doc.pdf",
                local_path=tmp_path / f"req_{packet_id}_doc.pdf",
                drive_file_id="drive_file_123",
                mime_type="application/pdf",
                parent_folder_id="folder_abc",
            )
        ]
    )


def _capture(tfd: TemplatedFileDownloader, packet_id: str = "123") -> dict:
    """Call download_packet and return the kwargs passed to download_matching_files."""
    captured = {}

    def fake_download(folder_id, search, download, **kwargs):
        captured["folder_id"] = folder_id
        captured["search"] = search
        captured["download"] = download
        captured.update(kwargs)
        return _success_result(tfd.destination_dir, packet_id)

    tfd.downloader.download_matching_files = fake_download
    tfd.download_packet(packet_id)
    return captured


# ---------------------------------------------------------------------------
# __init__ validation
# ---------------------------------------------------------------------------

class TestInit:
    def test_none_drive_raises_value_error(self, mock_drive):
        with pytest.raises(ValueError, match="drive service client must not be None"):
            TemplatedFileDownloader(drive=None, search_folder_id="folder_abc",
                                    destination_dir="./downloads", custom_save_filename_pattern="req_{id}_doc")

    def test_empty_folder_id_raises_configuration_error(self, mock_drive):
        with pytest.raises(ConfigurationError, match="search_folder_id must be a non-empty string"):
            TemplatedFileDownloader(drive=mock_drive, search_folder_id="   ",
                                    destination_dir="./downloads", custom_save_filename_pattern="req_{id}_doc")

    def test_empty_destination_dir_raises_configuration_error(self, mock_drive):
        with pytest.raises(ConfigurationError, match="destination_dir must be a non-empty string"):
            TemplatedFileDownloader(drive=mock_drive, search_folder_id="folder_abc",
                                    destination_dir="", custom_save_filename_pattern="req_{id}_doc")

    def test_empty_filename_pattern_raises_configuration_error(self, mock_drive):
        with pytest.raises(ConfigurationError, match="custom_save_filename_pattern must be a non-empty string"):
            TemplatedFileDownloader(drive=mock_drive, search_folder_id="folder_abc",
                                    destination_dir="./downloads", custom_save_filename_pattern=" \t ")

    def test_valid_args_succeeds(self, mock_drive, tmp_path):
        assert TemplatedFileDownloader(drive=mock_drive, search_folder_id="folder_abc",
                                       destination_dir=str(tmp_path), custom_save_filename_pattern="req_{id}_doc") is not None


# ---------------------------------------------------------------------------
# download_packet — input validation
# ---------------------------------------------------------------------------

class TestDownloadPacketValidation:
    def test_empty_id_raises_value_error(self, tfd):
        with pytest.raises(ValueError, match="packet id must not be blank"):
            tfd.download_packet("")

    def test_whitespace_id_raises_value_error(self, tfd):
        with pytest.raises(ValueError, match="packet id must not be blank"):
            tfd.download_packet("   ")


# ---------------------------------------------------------------------------
# download_packet — search term and filename formation
# ---------------------------------------------------------------------------

class TestDownloadPacketFormation:
    def test_search_term_uses_pa_prefix(self, tfd):
        assert _capture(tfd, "208988")["search"].search_term == "pa_208988"

    def test_whitespace_stripped_from_id(self, tfd):
        assert _capture(tfd, "  208988  ")["search"].search_term == "pa_208988"

    def test_custom_filename_formatted_with_id(self, tfd):
        assert _capture(tfd, "208988")["download"].custom_filename == "req_208988_doc"

    def test_folder_id_passed_correctly(self, tfd):
        assert _capture(tfd)["folder_id"] == "folder_abc"

    def test_destination_dir_passed_correctly(self, tfd):
        assert _capture(tfd)["download"].destination_dir == tfd.destination_dir


# ---------------------------------------------------------------------------
# download_packet — options passed through correctly
# ---------------------------------------------------------------------------

class TestDownloadPacketOptions:
    def test_match_mode_is_exact(self, tfd):
        assert _capture(tfd)["search"].match_mode == SearchMatchMode.EXACT

    def test_case_sensitive_is_false(self, tfd):
        assert _capture(tfd)["search"].case_sensitive is False

    def test_download_mode_is_all(self, tfd):
        assert _capture(tfd)["download_mode"] == DownloadMode.ALL

    def test_duplicate_strategy_is_skip(self, tfd):
        assert _capture(tfd)["download"].duplicate_strategy == DuplicateFilenameStrategy.SKIP

    def test_file_type_filter_is_pdf(self, tfd):
        assert "pdf" in _capture(tfd)["file_type"].extensions

    def test_traversal_is_recursive_and_unlimited(self, tfd):
        traversal = _capture(tfd)["traversal"]
        assert traversal.recursive is True
        assert traversal.max_depth == -1


# ---------------------------------------------------------------------------
# download_packet — result handling
# ---------------------------------------------------------------------------

class TestDownloadPacketResult:
    def test_returns_result_on_success(self, tfd, tmp_path):
        tfd.downloader.download_matching_files = lambda *a, **kw: _success_result(tmp_path)
        result = tfd.download_packet("123")
        assert result.success_count == 1

    def test_result_call_arguments(self, tfd, tmp_path):
        with patch.object(tfd.downloader, "download_matching_files",
                          return_value=_success_result(tmp_path)) as mock_call:
            tfd.download_packet("123")
            call_kwargs = mock_call.call_args.kwargs
            assert call_kwargs["folder_id"] == "folder_abc"
            assert call_kwargs["search"].search_term == "pa_123"
            assert call_kwargs["download"].destination_dir == tmp_path
            assert call_kwargs["download"].custom_filename == "req_123_doc"

    def test_no_match_raises_file_not_found(self, tfd):
        tfd.downloader.download_matching_files = lambda *a, **kw: DownloadResult()
        with pytest.raises(FileNotFoundError) as exc_info:
            tfd.download_packet("208988")
        assert "208988" in str(exc_info.value)
        assert "folder_abc" in str(exc_info.value)

    def test_skipped_duplicates_do_not_raise(self, tfd):
        skip_result = DownloadResult(skipped_duplicates=["/tmp/pa_123.pdf"])
        tfd.downloader.download_matching_files = lambda *a, **kw: skip_result
        result = tfd.download_packet("123")  # must not raise
        assert len(result.skipped_duplicates) == 1

    def test_errors_raise_download_error(self, tfd):
        bad = DownloadResult(errors=["API rate limit exceeded", "Disk write permission denied"])
        tfd.downloader.download_matching_files = lambda *a, **kw: bad
        with pytest.raises(DownloadError) as exc_info:
            tfd.download_packet("123")
        assert "Errors occurred while downloading packet 123" in str(exc_info.value)
        assert "API rate limit exceeded" in str(exc_info.value)
        assert "Disk write permission denied" in str(exc_info.value)

    def test_errors_take_priority_over_not_found(self, tfd):
        """When result has errors and nothing downloaded, DownloadError
        fires before FileNotFoundError — the attempt was made but failed."""
        bad = DownloadResult(errors=["some error"])
        tfd.downloader.download_matching_files = lambda *a, **kw: bad
        with pytest.raises(DownloadError):
            tfd.download_packet("123")
