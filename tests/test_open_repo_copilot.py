"""Tests for the open_repo_copilot module."""

import importlib.util
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


module_path = Path(__file__).resolve().parents[1] / "src" / "open_repo_copilot.py"
spec = importlib.util.spec_from_file_location("open_repo_copilot", module_path)
open_repo_copilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(open_repo_copilot)


def test_list_repos_only_returns_git_directories(tmp_path):
    """Only repositories containing a .git directory should be reported."""
    repo_a = tmp_path / "RepoA"
    repo_b = tmp_path / "RepoB"
    repo_c = tmp_path / "RepoC"
    repo_d = tmp_path / "not_repo"

    for directory in [repo_a, repo_b, repo_c]:
        directory.mkdir()
        (directory / ".git").mkdir()

    repo_d.mkdir()
    (tmp_path / "plain_file.txt").write_text("not a repo")

    assert sorted(open_repo_copilot.list_repos(str(tmp_path))) == ["RepoA", "RepoB", "RepoC"]


def test_get_active_branch_returns_branch_or_none(monkeypatch):
    """The active branch is returned when git succeeds, otherwise None."""
    success = SimpleNamespace(returncode=0, stdout="feature/login\n")
    failure = SimpleNamespace(returncode=128, stdout="fatal: not a git repo\n")

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", lambda *args, **kwargs: success)
    assert open_repo_copilot.get_active_branch("/tmp/repo") == "feature/login"

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", lambda *args, **kwargs: failure)
    assert open_repo_copilot.get_active_branch("/tmp/repo") is None

    def raise_oserror(*args, **kwargs):
        raise OSError("git missing")

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", raise_oserror)
    assert open_repo_copilot.get_active_branch("/tmp/repo") is None


def test_find_repo_handles_case_insensitive_exact_match():
    """Repository lookup should be case-insensitive and trim whitespace."""
    repos = ["Alpha", "beta", "Gamma"]

    assert open_repo_copilot.find_repo("alpha", repos) == "Alpha"
    assert open_repo_copilot.find_repo("  BETA  ", repos) == "beta"
    assert open_repo_copilot.find_repo("delta", repos) is None


def test_launch_copilot_runs_command_and_raises_on_error(monkeypatch, capsys):
    """The Copilot launcher runs the CLI and exits with the correct status."""
    calls = []

    def fake_run(command, cwd, check, shell):
        calls.append({"command": command, "cwd": cwd, "check": check, "shell": shell})
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", fake_run)
    monkeypatch.setattr(open_repo_copilot.os, "name", "posix")

    open_repo_copilot.launch_copilot("/tmp/repo")

    captured = capsys.readouterr()
    assert "Launching Copilot CLI in /tmp/repo" in captured.out
    assert calls[0]["command"] == ["copilot"]
    assert calls[0]["cwd"] == "/tmp/repo"
    assert calls[0]["check"] is True
    assert calls[0]["shell"] is False

    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("copilot not found")

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", raise_missing)
    with pytest.raises(SystemExit) as excinfo:
        open_repo_copilot.launch_copilot("/tmp/repo")
    assert excinfo.value.code == 1

    def raise_called(*args, **kwargs):
        raise subprocess.CalledProcessError(returncode=7, cmd=["copilot"])

    monkeypatch.setattr(open_repo_copilot.subprocess, "run", raise_called)
    with pytest.raises(SystemExit) as excinfo:
        open_repo_copilot.launch_copilot("/tmp/repo")
    assert excinfo.value.code == 7


def test_parse_args_reads_root_argument(monkeypatch):
    """The root path should be read from argv."""
    monkeypatch.setattr("sys.argv", ["open_repo_copilot.py", "/tmp/workspace"])
    args = open_repo_copilot.parse_args()
    assert args.root == "/tmp/workspace"


def test_main_selects_repo_by_name_and_launches(monkeypatch, tmp_path, capsys):
    """The main entry point chooses a repo from the menu and launches it."""
    root = tmp_path / "repos"
    root.mkdir()
    repo_dir = root / "AlphaRepo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    monkeypatch.setattr(open_repo_copilot.sys, "argv", ["open_repo_copilot.py", str(root)])

    def fake_input(_prompt):
        return "alpharepo"

    monkeypatch.setattr("builtins.input", fake_input)

    launched = []

    def fake_launch(path):
        launched.append(path)

    monkeypatch.setattr(open_repo_copilot, "launch_copilot", fake_launch)

    open_repo_copilot.main()

    assert launched == [str(repo_dir)]
    assert "Available repos:" in capsys.readouterr().out


def test_main_exits_on_blank_or_q_input(monkeypatch, tmp_path, capsys):
    """The main entry point exits cleanly on blank or quit input."""
    root = tmp_path / "repos"
    root.mkdir()
    repo_dir = root / "AlphaRepo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    monkeypatch.setattr(open_repo_copilot.sys, "argv", ["open_repo_copilot.py", str(root)])

    def fake_input(_prompt):
        return "q"

    monkeypatch.setattr("builtins.input", fake_input)

    launched = []

    def fake_launch(path):
        launched.append(path)

    monkeypatch.setattr(open_repo_copilot, "launch_copilot", fake_launch)

    open_repo_copilot.main()

    assert not launched
    assert "Exiting." in capsys.readouterr().out
