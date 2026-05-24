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
    def __init__(self, drive, search_folder_id, destination_dir, custom_save_filename_pattern):
        self.downloader = GoogleDriveFolderDownloader(drive)
        self.folder_id = search_folder_id
        self.target_file_name_pattern = "pa_{id}"
        self.file_type = FileTypeFilter(extensions=frozenset({"pdf"}))
        self.traversal_options = TraversalOptions(recursive=True, max_depth=-1)
        # self.download_options = DownloadOptions(
        #     destination_dir = Path(destination_dir),
        #     custom_filename=None,
        #     duplicate_strategy = DuplicateFilenameStrategy.SKIP,
        # )
        self.destination_dir = Path(destination_dir)
        self.custom_save_filename_pattern = custom_save_filename_pattern
        self.duplicate_strategy = DuplicateFilenameStrategy.SKIP
        self.download_mode = DownloadMode.ALL
        self.case_sensitive = False
        self.match_mode = SearchMatchMode.EXACT

    def download_packet(self, id):
        search_term = self.target_file_name_pattern.format(id=id)

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

        for meta in result.downloaded:
            print(meta.original_filename, meta.local_path, meta.drive_file_id)
    