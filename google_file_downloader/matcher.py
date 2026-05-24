"""Filename matching logic for Drive file search."""

from __future__ import annotations

from google_file_downloader.models import SearchMatchMode, SearchOptions


def normalize_for_compare(name: str, *, case_sensitive: bool) -> str:
    return name if case_sensitive else name.casefold()


def name_without_extension(filename: str) -> str:
    """Return the filename stem (extension is handled by FileTypeFilter)."""
    if "." not in filename:
        return filename
    stem, _ = filename.rsplit(".", 1)
    return stem


def filename_matches(name: str, options: SearchOptions) -> bool:
    """
    Return True if ``name`` satisfies the search options.

    Matching uses the filename stem only; extensions are handled separately
    via ``FileTypeFilter``.
    """
    left = normalize_for_compare(
        name_without_extension(name), case_sensitive=options.case_sensitive
    )
    right = normalize_for_compare(
        name_without_extension(options.search_term),
        case_sensitive=options.case_sensitive,
    )

    if options.match_mode == SearchMatchMode.EXACT:
        return left == right

    return right in left
