"""
benchmark_strategies.py
========================
Side-by-side comparison of two file-search strategies against a real
Google Drive folder structure.

  Strategy OLD  — Recursive DFS (walk every folder, list every child)
  Strategy NEW  — Search-First, Verify-Up (global name search, then walk up parents)

Measures:
  • Wall-clock time
  • Number of Google Drive API calls
  • Files found

Usage:
    python benchmark_strategies.py
    python benchmark_strategies.py --folder-id <ID> --search-term <TERM>
"""

import argparse
import os
import sys
import time
from functools import wraps
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_file_downloader.models import SearchOptions, TraversalOptions
from google_file_downloader.traversal import (
    iter_drive_files,
    iter_drive_files_strategy_a,
)

# ── Auth ──────────────────────────────────────────────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/drive"]


def authenticate():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as fh:
            fh.write(creds.to_json())
    return build("drive", "v3", credentials=creds)


# ── API call counter (wraps the service) ──────────────────────────────────────

class ApiCallCounter:
    """Transparent wrapper that counts every files().list / files().get call."""

    def __init__(self, real_service: Any) -> None:
        self._service = real_service
        self.call_count = 0

    def files(self):
        return _FilesProxy(self._service.files(), self)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


class _FilesProxy:
    def __init__(self, real_files: Any, counter: ApiCallCounter) -> None:
        self._files = real_files
        self._counter = counter

    def list(self, **kwargs):
        self._counter.call_count += 1
        return self._files.list(**kwargs)

    def get(self, **kwargs):
        self._counter.call_count += 1
        return self._files.get(**kwargs)

    def get_media(self, **kwargs):
        self._counter.call_count += 1
        return self._files.get_media(**kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._files, name)


# ── Benchmark runners ─────────────────────────────────────────────────────────

def run_old_strategy(service, folder_id: str, search_term: str) -> dict:
    """
    OLD: Recursive DFS — walks every folder top-down, listing all children.
    Then filters client-side by name.
    """
    counter = ApiCallCounter(service)
    traversal = TraversalOptions(recursive=True, max_depth=-1)

    t0 = time.perf_counter()
    found = []
    for file_meta in iter_drive_files(counter, folder_id, traversal):
        name = file_meta.get("name", "")
        if search_term.lower() in name.lower():
            found.append(file_meta)
    elapsed = time.perf_counter() - t0

    return {
        "strategy": "OLD — Recursive DFS",
        "api_calls": counter.call_count,
        "time_sec": elapsed,
        "files_found": len(found),
        "files": found,
    }


def run_new_strategy(service, folder_id: str, search_term: str) -> dict:
    """
    NEW: Search-First, Verify-Up — global Drive search, then verify ancestry.
    """
    counter = ApiCallCounter(service)
    search = SearchOptions(search_term=search_term)
    traversal = TraversalOptions(recursive=True, max_depth=-1)

    t0 = time.perf_counter()
    found = []
    for file_meta in iter_drive_files_strategy_a(counter, folder_id, search, traversal):
        found.append(file_meta)
    elapsed = time.perf_counter() - t0

    return {
        "strategy": "NEW — Search-First, Verify-Up",
        "api_calls": counter.call_count,
        "time_sec": elapsed,
        "files_found": len(found),
        "files": found,
    }


# ── Display ───────────────────────────────────────────────────────────────────

SEPARATOR = "=" * 70


def print_result(result: dict) -> None:
    print(f"\n  Strategy    : {result['strategy']}")
    print(f"  API calls   : {result['api_calls']}")
    print(f"  Time        : {result['time_sec']:.2f}s")
    print(f"  Files found : {result['files_found']}")
    if result["files"]:
        print(f"  Sample files:")
        for f in result["files"][:5]:
            print(f"    • {f.get('name')}  (parent: {f.get('parent_folder_name', '?')})")
        if len(result["files"]) > 5:
            print(f"    … and {len(result['files']) - 5} more")


def print_comparison(old: dict, new: dict) -> None:
    print(f"\n{SEPARATOR}")
    print("  COMPARISON SUMMARY")
    print(SEPARATOR)

    api_diff = old["api_calls"] - new["api_calls"]
    api_pct = (api_diff / old["api_calls"] * 100) if old["api_calls"] else 0

    time_diff = old["time_sec"] - new["time_sec"]
    speedup = (old["time_sec"] / new["time_sec"]) if new["time_sec"] > 0 else float("inf")

    print(f"\n  {'Metric':<20} {'OLD (DFS)':<20} {'NEW (Search+Verify)':<20} {'Improvement'}")
    print(f"  {'-' * 20} {'-' * 20} {'-' * 20} {'-' * 20}")
    print(f"  {'API calls':<20} {old['api_calls']:<20} {new['api_calls']:<20} {api_diff} fewer ({api_pct:.0f}%)")
    print(f"  {'Time (sec)':<20} {old['time_sec']:<20.2f} {new['time_sec']:<20.2f} {speedup:.1f}x faster")
    print(f"  {'Files found':<20} {old['files_found']:<20} {new['files_found']:<20} {'MATCH' if old['files_found'] == new['files_found'] else 'MISMATCH!'}")

    # Verify same files found
    old_ids = {f["id"] for f in old["files"]}
    new_ids = {f["id"] for f in new["files"]}
    if old_ids == new_ids:
        print(f"\n  [OK] Both strategies found exactly the same files.")
    else:
        only_old = old_ids - new_ids
        only_new = new_ids - old_ids
        if only_old:
            print(f"\n  [WARN] Only in OLD: {len(only_old)} files")
        if only_new:
            print(f"  [WARN] Only in NEW: {len(only_new)} files")

    print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Benchmark old vs new search strategy.")
    parser.add_argument(
        "--folder-id",
        default="1KekBkDvrZ69Jka1eoturicWKVhIjgldc",
        help="Root folder ID to search in (default: TestRoot).",
    )
    parser.add_argument(
        "--search-term",
        default="pa_177748",
        help="Filename to search for (default: pa_177748).",
    )
    args = parser.parse_args()

    print("[AUTH] Authenticating...")
    service = authenticate()
    print("[OK] Authenticated!\n")

    print(SEPARATOR)
    print(f"  Benchmark: Search for '{args.search_term}'")
    print(f"  Root folder: {args.folder_id}")
    print(SEPARATOR)

    # ── Run OLD strategy ──
    print(f"\n[...] Running OLD strategy (Recursive DFS) ...")
    old = run_old_strategy(service, args.folder_id, args.search_term)
    print_result(old)

    # ── Run NEW strategy ──
    print(f"\n[...] Running NEW strategy (Search-First, Verify-Up) ...")
    new = run_new_strategy(service, args.folder_id, args.search_term)
    print_result(new)

    # ── Compare ──
    print_comparison(old, new)


if __name__ == "__main__":
    main()
