from google_file_downloader.models import TraversalOptions
from google_file_downloader.traversal import iter_drive_files


def _folder(id_: str, name: str) -> dict:
    return {
        "id": id_,
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }


def _file(id_: str, name: str) -> dict:
    return {
        "id": id_,
        "name": name,
        "mimeType": "application/pdf",
        "parents": ["root"],
    }


class FakeFilesResource:
    def __init__(self, children: dict[str, list[dict]]) -> None:
        self._children = children

    def list(self, **kwargs):
        query: str = kwargs["q"]
        folder_id = query.split("'")[1]
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


def test_iter_files_non_recursive_only_root():
    service = FakeDriveService(
        {
            "root": [_file("f1", "a.pdf"), _folder("sub", "Sub")],
            "sub": [_file("f2", "b.pdf")],
        }
    )
    traversal = TraversalOptions(recursive=False, max_depth=0)
    names = [f["name"] for f in iter_drive_files(service, "root", traversal)]
    assert names == ["a.pdf"]


def test_iter_files_recursive_unlimited():
    service = FakeDriveService(
        {
            "root": [_file("f1", "a.pdf"), _folder("sub", "Sub")],
            "sub": [_file("f2", "b.pdf"), _folder("deep", "Deep")],
            "deep": [_file("f3", "c.pdf")],
        }
    )
    traversal = TraversalOptions(recursive=True, max_depth=-1)
    names = [f["name"] for f in iter_drive_files(service, "root", traversal)]
    assert names == ["a.pdf", "b.pdf", "c.pdf"]


def test_iter_files_max_depth_one():
    service = FakeDriveService(
        {
            "root": [_folder("sub", "Sub")],
            "sub": [_file("f2", "b.pdf"), _folder("deep", "Deep")],
            "deep": [_file("f3", "c.pdf")],
        }
    )
    traversal = TraversalOptions(recursive=True, max_depth=1)
    names = [f["name"] for f in iter_drive_files(service, "root", traversal)]
    assert names == ["b.pdf"]
