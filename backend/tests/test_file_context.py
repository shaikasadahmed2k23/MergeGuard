import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.file_context as file_context


@pytest.mark.asyncio
async def test_falls_back_to_diff_only_when_file_list_unavailable(monkeypatch):
    async def fake_get_pr_files(repo, pr_number):
        return []

    monkeypatch.setattr(file_context, "get_pr_files", fake_get_pr_files)

    result = await file_context.build_file_context("x/y", 1, "main", "diff --git a/x.py b/x.py")
    assert result.startswith("CODE DIFF:")


@pytest.mark.asyncio
async def test_includes_full_content_for_small_changed_files(monkeypatch):
    async def fake_get_pr_files(repo, pr_number):
        return [{"filename": "utils.py", "status": "modified"}]

    async def fake_get_file_content(repo, path, ref):
        return "def helper():\n    return 42\n"

    monkeypatch.setattr(file_context, "get_pr_files", fake_get_pr_files)
    monkeypatch.setattr(file_context, "get_file_content", fake_get_file_content)

    result = await file_context.build_file_context("x/y", 1, "feature/x", "diff --git a/utils.py b/utils.py")

    assert "FULL FILE" in result
    assert "utils.py" in result
    assert "def helper" in result


@pytest.mark.asyncio
async def test_skips_removed_files(monkeypatch):
    async def fake_get_pr_files(repo, pr_number):
        return [{"filename": "old.py", "status": "removed"}]

    called = {"hit": False}

    async def fake_get_file_content(repo, path, ref):
        called["hit"] = True
        return "shouldn't be fetched"

    monkeypatch.setattr(file_context, "get_pr_files", fake_get_pr_files)
    monkeypatch.setattr(file_context, "get_file_content", fake_get_file_content)

    result = await file_context.build_file_context("x/y", 1, "main", "diff")

    assert called["hit"] is False
    assert "old.py" not in result


@pytest.mark.asyncio
async def test_skips_files_over_the_size_cap(monkeypatch):
    async def fake_get_pr_files(repo, pr_number):
        return [{"filename": "huge.py", "status": "modified"}]

    async def fake_get_file_content(repo, path, ref):
        return "x" * (file_context.MAX_FULL_FILE_CHARS + 1)

    monkeypatch.setattr(file_context, "get_pr_files", fake_get_pr_files)
    monkeypatch.setattr(file_context, "get_file_content", fake_get_file_content)

    result = await file_context.build_file_context("x/y", 1, "main", "diff")

    assert "huge.py" not in result


@pytest.mark.asyncio
async def test_respects_max_files_with_full_content_limit(monkeypatch):
    files = [{"filename": f"file{i}.py", "status": "modified"} for i in range(10)]

    async def fake_get_pr_files(repo, pr_number):
        return files

    fetch_count = {"n": 0}

    async def fake_get_file_content(repo, path, ref):
        fetch_count["n"] += 1
        return "print(1)"

    monkeypatch.setattr(file_context, "get_pr_files", fake_get_pr_files)
    monkeypatch.setattr(file_context, "get_file_content", fake_get_file_content)

    await file_context.build_file_context("x/y", 1, "main", "diff")

    assert fetch_count["n"] <= file_context.MAX_FILES_WITH_FULL_CONTENT
