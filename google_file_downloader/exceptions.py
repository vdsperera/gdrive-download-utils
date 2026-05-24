"""Custom exceptions for Google Drive file download operations."""


class GoogleDriveDownloaderError(Exception):
    """Base exception for downloader errors."""


class ConfigurationError(GoogleDriveDownloaderError):
    """Raised when download or search configuration is invalid."""


class DriveApiError(GoogleDriveDownloaderError):
    """Raised when the Google Drive API returns an error."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class DownloadError(GoogleDriveDownloaderError):
    """Raised when a file download fails."""

    def __init__(
        self,
        message: str,
        *,
        file_id: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.file_id = file_id
        self.cause = cause
