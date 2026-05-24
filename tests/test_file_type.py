from google_file_downloader.file_type import file_matches_type
from google_file_downloader.models import FileTypeFilter


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
