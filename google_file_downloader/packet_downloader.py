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

class PacketDownloader:
    def __init__(self, drive, folder_id, destination_dir):
        self.downloader = GoogleDriveFolderDownloader(drive)
        self.folder_id = folder_id
        self.file_type = FileTypeFilter(extensions=frozenset({"pdf"}))
        self.traversal_options = TraversalOptions(recursive=True, max_depth=-1)
        self.download_options = DownloadOptions(
            destination_dir = Path(destination_dir),
            custom_filename=None,
            duplicate_strategy = DuplicateFilenameStrategy.SKIP,
        )
        self.download_mode = DownloadMode.ALL
        self.case_sensitive = False
        self.match_mode = SearchMatchMode.EXACT

    def download_packet(self, id):
        search_term = f"xx_{id}"

        search_options = SearchOptions(
            search_term=search_term,
            match_mode=self.match_mode,
            case_sensitive=self.case_sensitive,
        )

        result = self.downloader.download_matching_files(
            folder_id=self.folder_id,
            search=search_options,
            download=self.download_options,
            file_type=self.file_type,
            traversal=self.traversal_options,
            download_mode=self.download_mode,
        )

        for meta in result.downloaded:
            print(meta.original_filename, meta.local_path, meta.drive_file_id)
    