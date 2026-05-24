import pytest

from google_file_downloader.matcher import filename_matches
from google_file_downloader.models import SearchMatchMode, SearchOptions


@pytest.mark.parametrize(
    "name,term,mode,case_sensitive,expected",
    [
        ("Report.pdf", "Report", SearchMatchMode.EXACT, False, True),
        ("report.pdf", "Report", SearchMatchMode.EXACT, False, True),
        ("Report.pdf", "Report.pdf", SearchMatchMode.EXACT, False, True),
        ("pa_437301.pdf", "pa_437301", SearchMatchMode.EXACT, False, True),
        ("Report.pdf", "Repo", SearchMatchMode.PARTIAL, False, True),
        ("data.csv", "Report", SearchMatchMode.PARTIAL, False, False),
        ("Report.pdf", "report", SearchMatchMode.EXACT, True, False),
    ],
)
def test_filename_matches(name, term, mode, case_sensitive, expected):
    options = SearchOptions(
        search_term=term,
        match_mode=mode,
        case_sensitive=case_sensitive,
    )
    assert filename_matches(name, options) is expected


def test_search_term_empty_raises():
    with pytest.raises(ValueError):
        SearchOptions(search_term="   ")
