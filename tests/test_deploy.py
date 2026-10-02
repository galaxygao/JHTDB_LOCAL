"""Deployment routing tests: no network requests or production downloads."""
import importlib.util
from pathlib import Path
import subprocess

import pytest


spec = importlib.util.spec_from_file_location("deploy", Path(__file__).resolve().parents[1] / "deploy.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


def test_platforms_use_separate_environments():
    assert deploy.environment_python("win32").relative_to(deploy.PROJECT).as_posix() == ".venv-windows/Scripts/python.exe"
    assert deploy.environment_python("darwin").relative_to(deploy.PROJECT).as_posix() == ".venv-mac/bin/python"


def test_download_uses_pressure_cutout_not_server_gradient():
    commands = deploy.pipeline_commands(Path("python"), Path("pipeline.yaml"), 7, "download")
    assert [command[3] for command in commands[:3]] == ["doctor", "smoke", "cache"]
    assert commands[1][5] == "velocity"
    assert commands[-1][2:5] == ["jhtdb_pipeline.pressure_local", "--stage", "download"]
    assert all("--with-pressure-gradient" not in command for command in commands)
    assert all(command[-3:] == ["7", "--config", Path("pipeline.yaml")] for command in commands)


def test_failed_smoke_stops_before_download(tmp_path, monkeypatch):
    python = tmp_path / "python"
    python.touch()
    monkeypatch.setattr(deploy, "environment_python", lambda system: python)
    monkeypatch.setattr(deploy, "prepare_config", lambda *args: tmp_path / "pipeline.yaml")
    monkeypatch.setenv("JHTDB_DEPLOY_LOCKED", "1")
    calls = []

    def run(command, **kwargs):
        calls.append(command[3])
        if command[3] == "smoke":
            raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(deploy, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        deploy.main(["--stage", "all", "--skip-install", "--data-root", str(tmp_path)])
    assert calls == ["doctor", "smoke"]


def test_velocity_only_does_not_request_pressure():
    commands = deploy.pipeline_commands(Path("python"), Path("pipeline.yaml"), 1, "velocity")
    assert [command[3] for command in commands] == ["doctor", "smoke", "cache"]
    assert all("pressure_gradient" not in command and "--with-pressure-gradient" not in command for command in commands)


def test_background_detaches_and_does_not_recursively_spawn(tmp_path, monkeypatch):
    from types import SimpleNamespace
    calls = []

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(pid=12345)

    monkeypatch.setattr(deploy.subprocess, "Popen", spawn)
    assert deploy.main(["--background", "--skip-install", "--data-root", str(tmp_path)]) == 0
    command, options = calls[0]
    assert "--background" not in command
    assert "--skip-install" in command
    assert options["stdin"] == subprocess.DEVNULL
    assert options.get("start_new_session") or options.get("creationflags")
    assert (tmp_path / "deploy.pid").read_text() == "12345"
    assert (tmp_path / "deploy.log").is_file()
