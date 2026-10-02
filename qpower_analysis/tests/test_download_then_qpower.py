import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from filelock import FileLock


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("download_exit,expected", [(0, ["cache", "preflight", "analysis"]), (1, ["cache"])])
def test_job_stage_order_and_fail_stop(tmp_path, monkeypatch, download_exit, expected):
    runner = load_module("qpower_job_test", ROOT / "qpower_analysis/scripts/download_then_qpower.py")
    monkeypatch.setattr(runner, "FileLock", lambda path, timeout: FileLock(str(tmp_path / "test.lock"), timeout=timeout))
    calls = []

    def run(command, **kwargs):
        stage = "cache" if "cache" in command else ("preflight" if "--preflight-only" in command else "analysis")
        calls.append(stage)
        return SimpleNamespace(returncode=download_exit if stage == "cache" else 0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["runner", "--job-dir", str(tmp_path / "job")])
    assert runner.main() == download_exit
    assert calls == expected
    status = json.loads((tmp_path / "job/status.json").read_text())
    assert status["status"] == ("complete" if download_exit == 0 else "failed")


def test_analysis_end_to_end(tmp_path):
    analysis = load_module("qpower_smoke_test", ROOT / "qpower_analysis/qpower_analysis.py")
    rng = np.random.default_rng(17)
    velocity = tmp_path / "velocity.npy"
    gradient = tmp_path / "gradient.npy"
    np.save(velocity, rng.normal(size=(3, 8, 8, 8)).astype(np.float32))
    np.save(gradient, rng.normal(size=(3, 8, 8, 8)).astype(np.float32))
    config = {"frames": [{"frame": 1, "time": 0.0, "velocity_path": str(velocity),
                          "pressure_gradient_path": str(gradient), "pressure_gradient_keys": ["pressure_gradient"]}],
              "alphas": [1], "betas": [1], "n_conditional_bins": 4, "min_bin_count": 1,
              "output_root": str(tmp_path / "results")}
    result = analysis.run(config, analysis.preflight(config))
    assert (result / "run_summary.csv").is_file()
    assert (result / "frame_000001/overlays/alpha_1.0_beta_1.0.html").is_file()
    assert (result / "run_metadata.json").is_file()
