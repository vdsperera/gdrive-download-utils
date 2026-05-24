from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from google_file_downloader import (
    DownloadResult,
    DownloadedFileMetadata,
    PacketDownloader,
)
from google_file_downloader.exceptions import ConfigurationError, DownloadError


@pytest.fixture
def mock_drive() -> MagicMock:
    return MagicMock()


def test_packet_downloader_init_validation(mock_drive: MagicMock):
    # None drive should raise ValueError
    with pytest.raises(ValueError, match="drive service client must not be None"):
        PacketDownloader(
            drive=None,
            search_folder_id="folder_abc",
            destination_dir="./downloads",
            custom_save_filename_pattern="req_{id}_doc",
        )

    # Empty search_folder_id should raise ConfigurationError
    with pytest.raises(ConfigurationError, match="search_folder_id must be a non-empty string"):
        PacketDownloader(
            drive=mock_drive,
            search_folder_id="   ",
            destination_dir="./downloads",
            custom_save_filename_pattern="req_{id}_doc",
        )

    # Empty destination_dir should raise ConfigurationError
    with pytest.raises(ConfigurationError, match="destination_dir must be a non-empty string"):
        PacketDownloader(
            drive=mock_drive,
            search_folder_id="folder_abc",
            destination_dir="",
            custom_save_filename_pattern="req_{id}_doc",
        )

    # Empty custom_save_filename_pattern should raise ConfigurationError
    with pytest.raises(ConfigurationError, match="custom_save_filename_pattern must be a non-empty string"):
        PacketDownloader(
            drive=mock_drive,
            search_folder_id="folder_abc",
            destination_dir="./downloads",
            custom_save_filename_pattern=" \t ",
        )


def test_packet_downloader_download_packet_validation(mock_drive: MagicMock):
    pd = PacketDownloader(
        drive=mock_drive,
        search_folder_id="folder_abc",
        destination_dir="./downloads",
        custom_save_filename_pattern="req_{id}_doc",
    )

    # Empty packet id should raise ValueError
    with pytest.raises(ValueError, match="packet id must not be blank"):
        pd.download_packet("")

    with pytest.raises(ValueError, match="packet id must not be blank"):
        pd.download_packet("   ")


def test_packet_downloader_download_packet_success(mock_drive: MagicMock, tmp_path: Path):
    pd = PacketDownloader(
        drive=mock_drive,
        search_folder_id="folder_abc",
        destination_dir=str(tmp_path),
        custom_save_filename_pattern="req_{id}_doc",
    )

    expected_result = DownloadResult(
        downloaded=[
            DownloadedFileMetadata(
                original_filename="pa_123.pdf",
                downloaded_filename="req_123_doc.pdf",
                local_path=tmp_path / "req_123_doc.pdf",
                drive_file_id="drive_file_123",
                mime_type="application/pdf",
                parent_folder_id="folder_abc",
            )
        ]
    )

    with patch.object(
        pd.downloader,
        "download_matching_files",
        return_value=expected_result,
    ) as mock_download_matching:
        result = pd.download_packet("123")

        assert result == expected_result
        mock_download_matching.assert_called_once()
        
        # Check call arguments
        call_kwargs = mock_download_matching.call_args.kwargs
        assert call_kwargs["folder_id"] == "folder_abc"
        assert call_kwargs["search"].search_term == "pa_123"
        assert call_kwargs["download"].destination_dir == tmp_path
        assert call_kwargs["download"].custom_filename == "req_123_doc"


def test_packet_downloader_download_packet_failure(mock_drive: MagicMock, tmp_path: Path):
    pd = PacketDownloader(
        drive=mock_drive,
        search_folder_id="folder_abc",
        destination_dir=str(tmp_path),
        custom_save_filename_pattern="req_{id}_doc",
    )

    failure_result = DownloadResult(
        errors=["API rate limit exceeded", "Disk write permission denied"]
    )

    with patch.object(
        pd.downloader,
        "download_matching_files",
        return_value=failure_result,
    ):
        with pytest.raises(DownloadError) as exc_info:
            pd.download_packet("123")

        assert "Errors occurred while downloading packet 123" in str(exc_info.value)
        assert "API rate limit exceeded" in str(exc_info.value)
        assert "Disk write permission denied" in str(exc_info.value)
