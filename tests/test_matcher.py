import pytest

from google_file_downloader.matcher import filename_matches, name_without_extension
from google_file_downloader.models import SearchMatchMode, SearchOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _opts(term, mode=SearchMatchMode.PARTIAL, case_sensitive=False):
    return SearchOptions(search_term=term, match_mode=mode, case_sensitive=case_sensitive)


# ---------------------------------------------------------------------------
# SearchOptions validation
# ---------------------------------------------------------------------------

def test_search_term_empty_raises():
    with pytest.raises(ValueError):
        SearchOptions(search_term="   ")


# ---------------------------------------------------------------------------
# name_without_extension
# ---------------------------------------------------------------------------

class TestNameWithoutExtension:
    def test_removes_extension(self):
        assert name_without_extension("report.pdf") == "report"

    def test_no_extension_returns_full_name(self):
        assert name_without_extension("report") == "report"

    def test_multiple_dots_removes_last_only(self):
        assert name_without_extension("my.report.v2.pdf") == "my.report.v2"

    def test_empty_string(self):
        assert name_without_extension("") == ""


# ---------------------------------------------------------------------------
# filename_matches — parametrized existing cases kept intact
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,term,mode,case_sensitive,expected",
    [
        ("Report.pdf",    "Report",    SearchMatchMode.EXACT,   False, True),
        ("report.pdf",    "Report",    SearchMatchMode.EXACT,   False, True),
        ("Report.pdf",    "Report.pdf",SearchMatchMode.EXACT,   False, True),
        ("pa_437301.pdf", "pa_437301", SearchMatchMode.EXACT,   False, True),
        ("Report.pdf",    "Repo",      SearchMatchMode.PARTIAL, False, True),
        ("data.csv",      "Report",    SearchMatchMode.PARTIAL, False, False),
        ("Report.pdf",    "report",    SearchMatchMode.EXACT,   True,  False),
    ],
)
def test_filename_matches(name, term, mode, case_sensitive, expected):
    options = SearchOptions(search_term=term, match_mode=mode, case_sensitive=case_sensitive)
    assert filename_matches(name, options) is expected


# ---------------------------------------------------------------------------
# filename_matches — additional cases
# ---------------------------------------------------------------------------

class TestExactMatch:
    def test_partial_name_does_not_match_exact(self):
        assert filename_matches("monthly_report.pdf", _opts("report", SearchMatchMode.EXACT)) is False

    def test_superstring_does_not_match_exact(self):
        assert filename_matches("report.pdf", _opts("monthly_report", SearchMatchMode.EXACT)) is False

    def test_case_sensitive_passes_when_case_matches(self):
        assert filename_matches("Report.pdf", _opts("Report", SearchMatchMode.EXACT, case_sensitive=True)) is True


class TestPartialMatch:
    def test_substring_matches(self):
        assert filename_matches("monthly_report.pdf", _opts("report")) is True

    def test_case_sensitive_partial_fails_wrong_case(self):
        assert filename_matches("Monthly_Report.pdf", _opts("report", case_sensitive=True)) is False

    def test_case_sensitive_partial_passes_correct_case(self):
        assert filename_matches("Monthly_Report.pdf", _opts("Report", case_sensitive=True)) is True

    def test_extension_stripped_from_both_sides(self):
        # "report.pdf" search should match "report.docx" — extension ignored on both
        assert filename_matches("report.docx", _opts("report.pdf")) is True

    def test_filename_with_no_extension_matches(self):
        assert filename_matches("report", _opts("report")) is True