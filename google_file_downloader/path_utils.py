"""Local filesystem path helpers."""

from __future__ import annotations

from pathlib import Path

from google_file_downloader.models import DuplicateFilenameStrategy


def ensure_directory(path: Path) -> Path:
    """Create ``path`` and parents if missing; return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_target_path(
    destination_dir: Path,
    filename: str,
    strategy: DuplicateFilenameStrategy,
) -> tuple[Path, bool]:
    """
    Resolve the final download path for ``filename``.

    Returns ``(path, should_download)``. When ``should_download`` is False,
    the caller should skip (duplicate with SKIP strategy).
    """
    ensure_directory(destination_dir)
    target = destination_dir / filename

    if not target.exists():
        return target, True

    if strategy == DuplicateFilenameStrategy.OVERWRITE:
        return target, True

    if strategy == DuplicateFilenameStrategy.SKIP:
        return target, False

    if strategy == DuplicateFilenameStrategy.FAIL:
        raise FileExistsError(f"Destination file already exists: {target}")

    # RENAME
    stem = target.stem
    suffix = target.suffix
    counter = 1
    while target.exists():
        target = destination_dir / f"{stem} ({counter}){suffix}"
        counter += 1
    return target, True
