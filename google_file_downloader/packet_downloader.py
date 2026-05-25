from pathlib import Path

from google_file_downloader import (
    DownloadMode,
    DownloadOptions,
    DuplicateFilenameStrategy,
    FileTypeFilter,
    GoogleDriveFolderDownloader,
    SearchMatchMode,
    SearchOptions,
    TraversalOptions,
)

from google_file_downloader.models import DownloadResult

from google_file_downloader.exceptions import ConfigurationError, DownloadError

class PacketDownloader:
    def __init__(self, drive, search_folder_id: str,
                destination_dir: str, custom_save_filename_pattern: str):

        if not drive:
            raise ValueError("drive service client must not be None")
        if not search_folder_id or not search_folder_id.strip():
            raise ConfigurationError("search_folder_id must be a non-empty string")
        if not destination_dir or not destination_dir.strip():
            raise ConfigurationError("destination_dir must be a non-empty string")
        if not custom_save_filename_pattern or not custom_save_filename_pattern.strip():
            raise ConfigurationError("custom_save_filename_pattern must be a non-empty string")

        self.downloader = GoogleDriveFolderDownloader(drive)
        self.folder_id = search_folder_id
        self.target_file_name_pattern = "pa_{id}"
        self.file_type = FileTypeFilter(extensions=frozenset({"pdf"}))
        self.traversal_options = TraversalOptions(recursive=True, max_depth=-1)

        self.destination_dir = Path(destination_dir)
        self.custom_save_filename_pattern = custom_save_filename_pattern
        self.duplicate_strategy = DuplicateFilenameStrategy.SKIP
        self.download_mode = DownloadMode.ALL
        self.case_sensitive = False
        self.match_mode = SearchMatchMode.EXACT

    def download_packet(self, id) -> DownloadResult:
        normalized_id = str(id).strip()
        if not normalized_id:
            raise ValueError("packet id must not be blank")
        search_term = self.target_file_name_pattern.format(id=normalized_id)

        search_options = SearchOptions(
            search_term=search_term,
            match_mode=self.match_mode,
            case_sensitive=self.case_sensitive,
        )

        download_options = DownloadOptions(
            destination_dir = self.destination_dir,
            custom_filename=self.custom_save_filename_pattern.format(id=id),
            duplicate_strategy = self.duplicate_strategy,
        )

        result = self.downloader.download_matching_files(
            folder_id=self.folder_id,
            search=search_options,
            download=download_options,
            file_type=self.file_type,
            traversal=self.traversal_options,
            download_mode=self.download_mode,
        )

        if not result.downloaded and not result.skipped_duplicates:
            raise FileNotFoundError(
                f"No file found for packet {id} in folder {self.folder_id}"
            )

        # Raise exception or handle error reporting
        if result.errors:
            error_msg = (f"Errors occurred while downloading packet {id}: " +
                         "; ".join(result.errors))
            raise DownloadError(error_msg)
    
        return result