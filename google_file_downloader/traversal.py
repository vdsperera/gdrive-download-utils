"""Google Drive folder listing and recursive traversal."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from google_file_downloader.exceptions import DriveApiError
from google_file_downloader.models import DriveService, TraversalOptions, SearchOptions, FileTypeFilter

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
    escaped_folder_id = folder_id.replace("'", "\\'")
    query_parts = [f"'{escaped_folder_id}' in parents", "trashed = false"]
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
    visited_folders: set[str] = set()

    def walk(folder_id: str, depth: int, parent_name: str | None) -> Iterator[dict[str, Any]]:
        # Prevent infinite loops / multiple traversal paths
        if folder_id in visited_folders:
            logger.debug("Skipping already visited folder %s to avoid cycles", folder_id)
            return
        visited_folders.add(folder_id)

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


def iter_drive_files_strategy_a(
    service: DriveService,
    root_folder_id: str,
    search: SearchOptions,
    traversal: TraversalOptions,
) -> Iterator[dict[str, Any]]:
    """
    Search-First, Verify-Up (Strategy A):
    1. Query Google Drive API globally for files matching the search term.
    2. Walk up their parent hierarchy to verify if they are descendants of root_folder_id.
    3. Yield matching files enriched with parent_folder_id and parent_folder_name.
    """
    from google_file_downloader.matcher import name_without_extension

    search_stem = name_without_extension(search.search_term)
    escaped_stem = search_stem.replace("'", "\\'")

    query_parts = ["trashed = false"]
    if escaped_stem:
        query_parts.append(f"name contains '{escaped_stem}'")
    query = " and ".join(query_parts)

    # Fetch root folder name to match DFS/BFS traversal behavior for top-level files
    root_name = ""
    try:
        root_folder = (
            service.files()
            .get(
                fileId=root_folder_id,
                fields="name",
                supportsAllDrives=True,
            )
            .execute()
        )
        root_name = root_folder.get("name", "")
    except Exception as exc:
        logger.debug("Failed to fetch root folder metadata: %s", exc)

    # Cache for folder hierarchy: folder_id -> { "name": str, "parents": list, "is_descendant": bool, "depth": int }
    folder_cache: dict[str, dict[str, Any]] = {
        root_folder_id: {
            "name": root_name,
            "parents": [],
            "is_descendant": True,
            "depth": 0,
        }
    }

    def check_ancestry(folder_id: str, visited: set[str]) -> tuple[bool, int]:
        """
        Verify if folder_id is a descendant of root_folder_id.
        Returns (is_descendant, depth from root_folder_id).
        """
        if folder_id == root_folder_id:
            return True, 0
        if folder_id in visited:
            return False, -1
        visited.add(folder_id)

        if folder_id in folder_cache:
            entry = folder_cache[folder_id]
            if entry["is_descendant"] is not None:
                return entry["is_descendant"], entry["depth"]
        else:
            try:
                folder = (
                    service.files()
                    .get(
                        fileId=folder_id,
                        fields="id, name, parents",
                        supportsAllDrives=True,
                    )
                    .execute()
                )
                name = folder.get("name", "")
                parents = folder.get("parents", [])
            except Exception as exc:
                logger.debug("Failed to fetch metadata for folder %s: %s", folder_id, exc)
                name = ""
                parents = []

            folder_cache[folder_id] = {
                "name": name,
                "parents": parents,
                "is_descendant": None,
                "depth": -1,
            }

        entry = folder_cache[folder_id]
        is_descendant = False
        min_depth = -1

        for p in entry["parents"]:
            ok, d = check_ancestry(p, visited)
            if ok:
                is_descendant = True
                if min_depth == -1 or d + 1 < min_depth:
                    min_depth = d + 1

        entry["is_descendant"] = is_descendant
        entry["depth"] = min_depth
        return is_descendant, min_depth

    page_token: str | None = None
    max_depth = _effective_max_depth(traversal)

    try:
        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, parents)",
                    pageSize=CHILDREN_PAGE_SIZE,
                    pageToken=page_token,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )

            for item in response.get("files", []):
                if item.get("mimeType") == FOLDER_MIME:
                    continue

                parents = item.get("parents", [])
                if not parents:
                    continue

                for parent_id in parents:
                    is_descendant, depth_of_parent = check_ancestry(parent_id, set())
                    if not is_descendant:
                        continue

                    file_depth = depth_of_parent + 1

                    # Apply traversal limitations
                    if not traversal.recursive:
                        if file_depth != 1:
                            continue
                    else:
                        if max_depth >= 0 and file_depth > max_depth:
                            continue

                    parent_name = folder_cache.get(parent_id, {}).get("name")

                    enriched = dict(item)
                    enriched["parent_folder_id"] = parent_id
                    enriched["parent_folder_name"] = parent_name
                    yield enriched
                    break

            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as exc:
        raise DriveApiError(
            f"Failed to perform search query '{query}' on Drive", cause=exc
        ) from exc
