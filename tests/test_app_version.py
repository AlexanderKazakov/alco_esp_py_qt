import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from alco_esp import app_version


def fail_if_git_is_started(*_args, **_kwargs):
    raise AssertionError("git must not be started")


def test_build_version_file_is_used_first(monkeypatch, tmp_path):
    version_file = tmp_path / "build_version.txt"
    version_file.write_text("c29a21a-dirty\n", encoding="utf-8")
    monkeypatch.setattr(app_version, "BUILD_VERSION_FILE_PATH", str(version_file))
    monkeypatch.setattr(app_version.subprocess, "run", fail_if_git_is_started)

    assert app_version.get_app_version() == "c29a21a-dirty"


@pytest.mark.parametrize("file_content", [None, ""], ids=["no_file", "empty_file"])
def test_build_without_version_file_returns_unknown_and_does_not_start_git(monkeypatch, tmp_path, file_content):
    version_file = tmp_path / "build_version.txt"
    if file_content is not None:
        version_file.write_text(file_content, encoding="utf-8")
    monkeypatch.setattr(app_version, "BUILD_VERSION_FILE_PATH", str(version_file))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(app_version.subprocess, "run", fail_if_git_is_started)

    assert app_version.get_app_version() == "unknown"


def test_source_run_uses_git_describe(monkeypatch, tmp_path):
    monkeypatch.setattr(app_version, "BUILD_VERSION_FILE_PATH", str(tmp_path / "missing.txt"))
    git_calls = []

    def fake_run(command, **kwargs):
        git_calls.append((command, kwargs["cwd"]))
        return SimpleNamespace(returncode=0, stdout="c29a21a\n")

    monkeypatch.setattr(app_version.subprocess, "run", fake_run)

    assert app_version.get_app_version() == "c29a21a"
    assert git_calls == [(["git", "describe", "--always", "--dirty"], app_version.APP_ROOT_DIR)]


@pytest.mark.parametrize(
    "fake_run",
    [
        pytest.param(lambda *_args, **_kwargs: SimpleNamespace(returncode=128, stdout=""), id="not_a_git_checkout"),
        pytest.param(lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError("git")), id="git_not_installed"),
        pytest.param(
            lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("git", 5)), id="git_timeout"
        ),
    ],
)
def test_source_run_returns_unknown_when_git_fails(monkeypatch, tmp_path, fake_run):
    monkeypatch.setattr(app_version, "BUILD_VERSION_FILE_PATH", str(tmp_path / "missing.txt"))
    monkeypatch.setattr(app_version.subprocess, "run", fake_run)

    assert app_version.get_app_version() == "unknown"


@pytest.mark.skipif(
    shutil.which("git") is None or not (Path(app_version.APP_ROOT_DIR).parent / ".git").exists(),
    reason="Needs git and a git checkout",
)
def test_source_run_in_this_checkout_returns_the_head_commit():
    head_commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=app_version.APP_ROOT_DIR, capture_output=True, text=True, check=True
    ).stdout.strip()

    version = app_version.get_app_version()

    assert head_commit.startswith(version.removesuffix("-dirty"))
