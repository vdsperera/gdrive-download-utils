from pathlib import Path

import pytest

from google_file_downloader.models import DuplicateFilenameStrategy
from google_file_downloader.path_utils import ensure_directory, resolve_target_path


def test_ensure_directory_creates_nested(tmp_path: Path):
    target = tmp_path / "a" / "b"
    ensure_directory(target)
    assert target.is_dir()


def test_resolve_rename_on_duplicate(tmp_path: Path):
    existing = tmp_path / "file.txt"
    existing.write_text("old")

    path, should = resolve_target_path(
        tmp_path, "file.txt", DuplicateFilenameStrategy.RENAME
    )
    assert should is True
    assert path.name == "file (1).txt"


def test_resolve_skip_duplicate(tmp_path: Path):
    (tmp_path / "file.txt").write_text("old")
    path, should = resolve_target_path(
        tmp_path, "file.txt", DuplicateFilenameStrategy.SKIP
    )
    assert should is False


def test_resolve_fail_on_duplicate(tmp_path: Path):
    (tmp_path / "file.txt").write_text("old")
    with pytest.raises(FileExistsError):
        resolve_target_path(tmp_path, "file.txt", DuplicateFilenameStrategy.FAIL)
