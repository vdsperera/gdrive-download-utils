from pathlib import Path

import pytest

from google_file_downloader.models import DuplicateFilenameStrategy
from google_file_downloader.path_utils import ensure_directory, resolve_target_path


# ---------------------------------------------------------------------------
# Existing cases kept intact
# ---------------------------------------------------------------------------

def test_ensure_directory_creates_nested(tmp_path: Path):
    target = tmp_path / "a" / "b"
    ensure_directory(target)
    assert target.is_dir()


def test_resolve_rename_on_duplicate(tmp_path: Path):
    (tmp_path / "file.txt").write_text("old")
    path, should = resolve_target_path(tmp_path, "file.txt", DuplicateFilenameStrategy.RENAME)
    assert should is True
    assert path.name == "file (1).txt"


def test_resolve_skip_duplicate(tmp_path: Path):
    (tmp_path / "file.txt").write_text("old")
    path, should = resolve_target_path(tmp_path, "file.txt", DuplicateFilenameStrategy.SKIP)
    assert should is False


def test_resolve_fail_on_duplicate(tmp_path: Path):
    (tmp_path / "file.txt").write_text("old")
    with pytest.raises(FileExistsError):
        resolve_target_path(tmp_path, "file.txt", DuplicateFilenameStrategy.FAIL)


# ---------------------------------------------------------------------------
# Additional cases
# ---------------------------------------------------------------------------

class TestEnsureDirectory:
    def test_existing_directory_no_error(self, tmp_path):
        ensure_directory(tmp_path)  # already exists — should not raise
        assert tmp_path.exists()

    def test_returns_path(self, tmp_path):
        result = ensure_directory(tmp_path)
        assert result == tmp_path


class TestNewFile:
    def test_new_file_should_download_for_all_strategies(self, tmp_path):
        for strategy in DuplicateFilenameStrategy:
            path, should = resolve_target_path(tmp_path, f"new_{strategy}.pdf", strategy)
            assert should is True

    def test_destination_dir_created_when_missing(self, tmp_path):
        new_dir = tmp_path / "sub" / "downloads"
        resolve_target_path(new_dir, "file.pdf", DuplicateFilenameStrategy.RENAME)
        assert new_dir.exists()


class TestOverwrite:
    def test_existing_file_overwrite_returns_true(self, tmp_path):
        (tmp_path / "file.pdf").write_bytes(b"old")
        path, should = resolve_target_path(tmp_path, "file.pdf", DuplicateFilenameStrategy.OVERWRITE)
        assert should is True
        assert path == tmp_path / "file.pdf"


class TestSkip:
    def test_new_file_skip_still_downloads(self, tmp_path):
        _, should = resolve_target_path(tmp_path, "new.pdf", DuplicateFilenameStrategy.SKIP)
        assert should is True


class TestFail:
    def test_new_file_no_error(self, tmp_path):
        path, should = resolve_target_path(tmp_path, "new.pdf", DuplicateFilenameStrategy.FAIL)
        assert should is True


class TestRename:
    def test_increments_past_one_when_both_exist(self, tmp_path):
        (tmp_path / "file.txt").write_text("v1")
        (tmp_path / "file (1).txt").write_text("v2")
        path, should = resolve_target_path(tmp_path, "file.txt", DuplicateFilenameStrategy.RENAME)
        assert path.name == "file (2).txt"
        assert should is True

    def test_extension_preserved_on_rename(self, tmp_path):
        (tmp_path / "data.csv").write_bytes(b"x")
        path, _ = resolve_target_path(tmp_path, "data.csv", DuplicateFilenameStrategy.RENAME)
        assert path.suffix == ".csv"

    def test_file_without_extension_renamed(self, tmp_path):
        (tmp_path / "report").write_bytes(b"x")
        path, _ = resolve_target_path(tmp_path, "report", DuplicateFilenameStrategy.RENAME)
        assert path.name == "report (1)"