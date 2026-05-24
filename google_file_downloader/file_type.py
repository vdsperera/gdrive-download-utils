"""File type validation using extension and MIME type."""

from __future__ import annotations

from google_file_downloader.mime import extension_from_filename, mime_for_extension
from google_file_downloader.models import FileTypeFilter


def file_matches_type(
    filename: str,
    mime_type: str | None,
    file_filter: FileTypeFilter | None,
) -> bool:
    """
    Return True if no filter is active or the file satisfies the filter.

    When both extensions and MIME types are configured, either match is sufficient.
    """
    if file_filter is None or not file_filter.is_active:
        return True

    ext = extension_from_filename(filename)
    ext_ok = bool(ext and ext in file_filter.extensions)

    mime = (mime_type or "").lower()
    mime_ok = bool(mime and mime in {m.lower() for m in file_filter.mime_types})

    if not file_filter.extensions and file_filter.mime_types:
        return mime_ok
    if file_filter.extensions and not file_filter.mime_types:
        return ext_ok

    return ext_ok or mime_ok


def resolve_mime_types_for_extensions(extensions: frozenset[str]) -> frozenset[str]:
    """Expand extensions to known MIME types for Drive API queries."""
    resolved: set[str] = set()
    for ext in extensions:
        mime = mime_for_extension(ext)
        if mime:
            resolved.add(mime)
    return frozenset(resolved)
