import pytest

from google_file_downloader.file_type import file_matches_type, resolve_mime_types_for_extensions
from google_file_downloader.models import FileTypeFilter


# ---------------------------------------------------------------------------
# Existing cases kept intact
# ---------------------------------------------------------------------------

def test_extension_only_filter():
    filt = FileTypeFilter(extensions=frozenset({"pdf"}))
    assert file_matches_type("doc.pdf", "application/pdf", filt)
    assert not file_matches_type("doc.csv", "text/csv", filt)


def test_mime_only_filter():
    filt = FileTypeFilter(mime_types=frozenset({"text/csv"}))
    assert file_matches_type("data", "text/csv", filt)
    assert not file_matches_type("data", "text/plain", filt)


def test_combined_filter_accepts_either():
    filt = FileTypeFilter(
        extensions=frozenset({"pdf"}),
        mime_types=frozenset({"text/csv"}),
    )
    assert file_matches_type("x.csv", "text/csv", filt)
    assert file_matches_type("x.pdf", "application/pdf", filt)
    assert not file_matches_type("x.txt", "text/plain", filt)


def test_no_filter_accepts_all():
    assert file_matches_type("anything.bin", None, None)
    assert file_matches_type("anything.bin", None, FileTypeFilter())


# ---------------------------------------------------------------------------
# Additional cases
# ---------------------------------------------------------------------------

class TestExtensionFilter:
    def test_uppercase_filename_extension_normalised(self):
        filt = FileTypeFilter(extensions=frozenset({"pdf"}))
        assert file_matches_type("report.PDF", "application/pdf", filt) is True

    def test_dot_prefixed_extension_in_filter_normalised(self):
        filt = FileTypeFilter(extensions=frozenset({".pdf"}))
        assert file_matches_type("report.pdf", "application/pdf", filt) is True

    def test_filename_with_no_extension_fails(self):
        filt = FileTypeFilter(extensions=frozenset({"pdf"}))
        assert file_matches_type("report", None, filt) is False

    def test_multiple_allowed_extensions(self):
        filt = FileTypeFilter(extensions=frozenset({"pdf", "xlsx"}))
        assert file_matches_type("report.pdf", None, filt) is True
        assert file_matches_type("data.xlsx", None, filt) is True
        assert file_matches_type("notes.csv", None, filt) is False


class TestMimeFilter:
    def test_none_mime_fails_mime_only_filter(self):
        filt = FileTypeFilter(mime_types=frozenset({"application/pdf"}))
        assert file_matches_type("report.pdf", None, filt) is False

    def test_mime_comparison_case_insensitive(self):
        filt = FileTypeFilter(mime_types=frozenset({"application/pdf"}))
        assert file_matches_type("report.pdf", "Application/PDF", filt) is True


class TestInactiveFilter:
    def test_empty_filter_is_inactive(self):
        assert FileTypeFilter().is_active is False

    def test_inactive_filter_always_passes(self):
        filt = FileTypeFilter()
        assert file_matches_type("anything.xyz", "unknown/type", filt) is True


class TestResolveMimeTypesForExtensions:
    def test_known_extension_resolves(self):
        result = resolve_mime_types_for_extensions(frozenset({"pdf"}))
        assert "application/pdf" in result

    def test_multiple_known_extensions(self):
        result = resolve_mime_types_for_extensions(frozenset({"pdf", "csv"}))
        assert "application/pdf" in result
        assert "text/csv" in result

    def test_unknown_extension_excluded(self):
        assert len(resolve_mime_types_for_extensions(frozenset({"xyz"}))) == 0

    def test_empty_input_returns_empty(self):
        assert resolve_mime_types_for_extensions(frozenset()) == frozenset()