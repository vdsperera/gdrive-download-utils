"""MIME type helpers and common extension mappings."""

from __future__ import annotations

COMMON_EXTENSION_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "txt": "text/plain",
    "json": "application/json",
    "xml": "application/xml",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "zip": "application/zip",
}


def extension_from_filename(filename: str) -> str | None:
    """Return lowercase extension without dot, or None if absent."""
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext or None


def mime_for_extension(extension: str) -> str | None:
    """Return a common MIME type for a normalized extension, if known."""
    return COMMON_EXTENSION_TO_MIME.get(extension.lower().lstrip("."))


def extensions_from_filter(extensions: frozenset[str]) -> frozenset[str]:
    """Normalize extension strings for comparison."""
    return frozenset(ext.lower().lstrip(".") for ext in extensions)
