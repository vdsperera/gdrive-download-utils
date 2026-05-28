import pytest
from unittest.mock import MagicMock

from google_file_downloader.exceptions import DriveApiError
from google_file_downloader.models import TraversalOptions, SearchOptions
from google_file_downloader.traversal import iter_drive_files, iter_drive_files_strategy_a

FOLDER_MIME = "application/vnd.google-apps.folder"


# ---------------------------------------------------------------------------
# Fake Drive service (no MagicMock needed for happy-path tests)
# ---------------------------------------------------------------------------

def _folder(id_: str, name: str) -> dict:
    return {"id": id_, "name": name, "mimeType": FOLDER_MIME}


def _file(id_: str, name: str) -> dict:
    return {"id": id_, "name": name, "mimeType": "application/pdf", "parents": ["root"]}


class FakeFilesResource:
    def __init__(self, children: dict[str, list[dict]]) -> None:
        self._children = children

    def list(self, **kwargs):
        folder_id = kwargs["q"].split("'")[1]
        return FakeListRequest(self._children.get(folder_id, []))


class FakeListRequest:
    def __init__(self, files: list[dict]) -> None:
        self._files = files

    def execute(self) -> dict:
        return {"files": self._files}


class FakeDriveService:
    def __init__(self, children: dict[str, list[dict]]) -> None:
        self._children = children

    def files(self) -> FakeFilesResource:
        return FakeFilesResource(self._children)


# ---------------------------------------------------------------------------
# Existing cases kept intact
# ---------------------------------------------------------------------------

def test_iter_files_non_recursive_only_root():
    service = FakeDriveService({
        "root": [_file("f1", "a.pdf"), _folder("sub", "Sub")],
        "sub":  [_file("f2", "b.pdf")],
    })
    names = [f["name"] for f in iter_drive_files(service, "root", TraversalOptions(recursive=False))]
    assert names == ["a.pdf"]


def test_iter_files_recursive_unlimited():
    service = FakeDriveService({
        "root": [_file("f1", "a.pdf"), _folder("sub", "Sub")],
        "sub":  [_file("f2", "b.pdf"), _folder("deep", "Deep")],
        "deep": [_file("f3", "c.pdf")],
    })
    names = [f["name"] for f in iter_drive_files(service, "root", TraversalOptions(recursive=True, max_depth=-1))]
    assert names == ["a.pdf", "b.pdf", "c.pdf"]


def test_iter_files_max_depth_one():
    service = FakeDriveService({
        "root": [_folder("sub", "Sub")],
        "sub":  [_file("f2", "b.pdf"), _folder("deep", "Deep")],
        "deep": [_file("f3", "c.pdf")],
    })
    names = [f["name"] for f in iter_drive_files(service, "root", TraversalOptions(recursive=True, max_depth=1))]
    assert names == ["b.pdf"]


# ---------------------------------------------------------------------------
# Additional cases
# ---------------------------------------------------------------------------

class TestFlatFolder:
    def test_empty_folder_yields_nothing(self):
        service = FakeDriveService({"root": []})
        assert list(iter_drive_files(service, "root", TraversalOptions())) == []

    def test_subfolders_not_yielded_as_files(self):
        service = FakeDriveService({"root": [_folder("sub", "Sub"), _file("f1", "root.pdf")]})
        results = list(iter_drive_files(service, "root", TraversalOptions()))
        assert len(results) == 1
        assert results[0]["id"] == "f1"

    def test_parent_folder_id_set_on_yielded_files(self):
        service = FakeDriveService({"root": [_file("f1", "a.pdf")]})
        results = list(iter_drive_files(service, "root", TraversalOptions()))
        assert results[0]["parent_folder_id"] == "root"


class TestRecursiveTraversal:
    def test_parent_folder_name_set_in_subfolder(self):
        service = FakeDriveService({
            "root": [_folder("sub1", "MySubFolder")],
            "sub1": [_file("f1", "deep.pdf")],
        })
        results = list(iter_drive_files(service, "root", TraversalOptions(recursive=True, max_depth=-1)))
        assert results[0]["parent_folder_name"] == "MySubFolder"

    def test_max_depth_two(self):
        service = FakeDriveService({
            "root":  [_folder("l1", "L1")],
            "l1":    [_folder("l2", "L2"), _file("f1", "l1.pdf")],
            "l2":    [_folder("l3", "L3"), _file("f2", "l2.pdf")],
            "l3":    [_file("f3", "l3.pdf")],
        })
        opts = TraversalOptions(recursive=True, max_depth=2)
        names = {f["name"] for f in iter_drive_files(service, "root", opts)}
        assert "l1.pdf" in names
        assert "l2.pdf" in names
        assert "l3.pdf" not in names  # depth 3 — excluded


class TestCycleDetection:
    def test_cycle_does_not_cause_infinite_loop(self):
        """Folder A → Folder B → Folder A (shortcut). Must terminate."""
        call_count = {"n": 0}

        class CyclicFilesResource:
            def list(self_, **kwargs):
                call_count["n"] += 1
                folder_id = kwargs["q"].split("'")[1]
                if folder_id == "root":
                    return FakeListRequest([_folder("A", "FolderA"), _file("f1", "root.pdf")])
                elif folder_id == "A":
                    return FakeListRequest([_folder("B", "FolderB")])
                elif folder_id == "B":
                    return FakeListRequest([_folder("A", "FolderA"), _file("f2", "deep.pdf")])
                return FakeListRequest([])

        class CyclicService:
            def files(self_):
                return CyclicFilesResource()

        opts = TraversalOptions(recursive=True, max_depth=-1)
        results = list(iter_drive_files(CyclicService(), "root", opts))

        ids = {r["id"] for r in results}
        assert "f1" in ids
        assert "f2" in ids
        assert call_count["n"] == 3  # root + A + B; A not revisited

    def test_shared_subfolder_visited_only_once(self):
        """Two parent folders both link to the same subfolder — must traverse it once."""
        visit_count = {"shared": 0}

        class SharedFilesResource:
            def list(self_, **kwargs):
                folder_id = kwargs["q"].split("'")[1]
                if folder_id == "root":
                    return FakeListRequest([_folder("A", "A"), _folder("B", "B")])
                elif folder_id in ("A", "B"):
                    return FakeListRequest([_folder("shared", "Shared")])
                elif folder_id == "shared":
                    visit_count["shared"] += 1
                    return FakeListRequest([_file("f1", "shared.pdf")])
                return FakeListRequest([])

        class SharedService:
            def files(self_):
                return SharedFilesResource()

        opts = TraversalOptions(recursive=True, max_depth=-1)
        list(iter_drive_files(SharedService(), "root", opts))
        assert visit_count["shared"] == 1


class TestPagination:
    def test_multiple_pages_assembled(self):
        service = MagicMock()
        service.files().list().execute.side_effect = [
            {"files": [_file("f1", "a.pdf")], "nextPageToken": "tok1"},
            {"files": [_file("f2", "b.pdf")], "nextPageToken": None},
        ]
        results = list(iter_drive_files(service, "root", TraversalOptions()))
        assert {r["id"] for r in results} == {"f1", "f2"}


class TestErrorHandling:
    def test_api_error_raises_drive_api_error(self):
        service = MagicMock()
        service.files().list().execute.side_effect = Exception("500 Internal Server Error")
        with pytest.raises(DriveApiError):
            list(iter_drive_files(service, "root", TraversalOptions()))

    def test_drive_api_error_includes_folder_id(self):
        service = MagicMock()
        service.files().list().execute.side_effect = Exception("timeout")
        with pytest.raises(DriveApiError) as exc_info:
            list(iter_drive_files(service, "myfolder123", TraversalOptions()))
        assert "myfolder123" in str(exc_info.value)


class TestTraversalOptionsValidation:
    def test_max_depth_positive_requires_recursive(self):
        with pytest.raises(ValueError):
            TraversalOptions(recursive=False, max_depth=2)

    def test_max_depth_minus_one_requires_recursive(self):
        with pytest.raises(ValueError):
            TraversalOptions(recursive=False, max_depth=-1)

    def test_max_depth_below_minus_one_invalid(self):
        with pytest.raises(ValueError):
            TraversalOptions(recursive=True, max_depth=-2)


class TestStrategyATraversal:
    def test_strategy_a_finds_nested_file(self):
        service = MagicMock()
        # Mock root folder query and parent folder queries
        service.files().get().execute.side_effect = [
            {"id": "root", "name": "RootFolder", "parents": []},  # root folder
            {"id": "sub1", "name": "SubFolder", "parents": ["root"]},  # parent of file
        ]
        # Mock global list query returning the file
        service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "f1",
                    "name": "pa_208988.pdf",
                    "mimeType": "application/pdf",
                    "parents": ["sub1"],
                }
            ],
            "nextPageToken": None,
        }

        results = list(
            iter_drive_files_strategy_a(
                service,
                "root",
                SearchOptions(search_term="pa_208988"),
                TraversalOptions(recursive=True, max_depth=-1),
            )
        )

        assert len(results) == 1
        res = results[0]
        assert res["id"] == "f1"
        assert res["name"] == "pa_208988.pdf"
        assert res["parent_folder_id"] == "sub1"
        assert res["parent_folder_name"] == "SubFolder"

    def test_strategy_a_respects_max_depth(self):
        service = MagicMock()
        # Mock folder parents:
        # root -> sub1 (depth 1) -> sub2 (depth 2) -> f1
        service.files().get().execute.side_effect = [
            {"id": "root", "name": "RootFolder", "parents": []},  # root folder
            {"id": "sub2", "name": "Sub2", "parents": ["sub1"]},  # parent of f1
            {"id": "sub1", "name": "Sub1", "parents": ["root"]},  # parent of sub2
        ]
        service.files().list().execute.return_value = {
            "files": [
                {
                    "id": "f1",
                    "name": "pa_208988.pdf",
                    "mimeType": "application/pdf",
                    "parents": ["sub2"],
                }
            ],
            "nextPageToken": None,
        }

        # recursive=True, max_depth=1 (only sub1 allowed, not sub2/f1)
        results = list(
            iter_drive_files_strategy_a(
                service,
                "root",
                SearchOptions(search_term="pa_208988"),
                TraversalOptions(recursive=True, max_depth=1),
            )
        )
        assert len(results) == 0

        # Now test with max_depth=2 (sub2/f1 allowed)
        # reset mocks
        service.files().get().execute.side_effect = [
            {"id": "root", "name": "RootFolder", "parents": []},
            {"id": "sub2", "name": "Sub2", "parents": ["sub1"]},
            {"id": "sub1", "name": "Sub1", "parents": ["root"]},
        ]
        results2 = list(
            iter_drive_files_strategy_a(
                service,
                "root",
                SearchOptions(search_term="pa_208988"),
                TraversalOptions(recursive=True, max_depth=3),
            )
        )
        assert len(results2) == 1