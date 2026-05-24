"""Google Drive folder listing and recursive traversal."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from google_file_downloader.exceptions import DriveApiError
from google_file_downloader.models import DriveService, TraversalOptions

logger = logging.getLogger(__name__)

FOLDER_MIME = "application/vnd.google-apps.folder"
FILE_FIELDS = "nextPageToken, files(id, name, mimeType, parents)"
CHILDREN_PAGE_SIZE = 100


def _list_children(
    service: DriveService,
    folder_id: str,
    *,
    mime_query: str | None = None,
) -> list[dict[str, Any]]:
    """List non-trashed children of a folder."""
    query_parts = [f"'{folder_id}' in parents", "trashed = false"]
    if mime_query:
        query_parts.append(mime_query)
    query = " and ".join(query_parts)

    items: list[dict[str, Any]] = []
    page_token: str | None = None

    try:
        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields=FILE_FIELDS,
                    pageSize=CHILDREN_PAGE_SIZE,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            items.extend(response.get("files", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as exc:
        raise DriveApiError(
            f"Failed to list children of folder {folder_id}", cause=exc
        ) from exc

    return items


def _effective_max_depth(options: TraversalOptions) -> int:
    if not options.recursive:
        return 0
    return options.max_depth


def iter_drive_files(
    service: DriveService,
    root_folder_id: str,
    traversal: TraversalOptions,
    *,
    folder_names: dict[str, str] | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Yield file metadata dicts under ``root_folder_id`` per traversal rules.

    Each yielded dict includes ``parent_folder_id`` and optional
    ``parent_folder_name`` for downstream metadata.
    """
    max_depth = _effective_max_depth(traversal)
    names = folder_names if folder_names is not None else {}

    def walk(folder_id: str, depth: int, parent_name: str | None) -> Iterator[dict[str, Any]]:
        if depth > 0 and max_depth >= 0 and depth > max_depth:
            return

        logger.debug("Listing folder %s at depth %d", folder_id, depth)
        children = _list_children(service, folder_id)

        subfolders: list[dict[str, Any]] = []
        for item in children:
            mime = item.get("mimeType", "")
            if mime == FOLDER_MIME:
                subfolders.append(item)
                names[item["id"]] = item.get("name", "")
                continue

            enriched = dict(item)
            enriched["parent_folder_id"] = folder_id
            enriched["parent_folder_name"] = parent_name
            yield enriched

        if not traversal.recursive:
            return

        next_depth = depth + 1
        if max_depth >= 0 and next_depth > max_depth:
            return

        for folder in subfolders:
            folder_name = folder.get("name")
            yield from walk(folder["id"], next_depth, folder_name)

    yield from walk(root_folder_id, 0, names.get(root_folder_id))
