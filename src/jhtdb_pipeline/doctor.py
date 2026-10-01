from __future__ import annotations

import importlib.metadata
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import token_source
from .config import PipelineConfig
from .validation import atomic_json


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_run_record(cfg: PipelineConfig, time_index: int) -> dict[str, Any]:
    """Create a durable local run record; local caches do not expire."""
    path = cfg.run_path(time_index) / "run.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    payload = {
        "time_index": time_index,
        "created_at": _utcnow().isoformat(),
        "storage": "local",
        "expires_at": None,
    }
    atomic_json(path, payload)
    return payload


def _space(path: Path) -> dict[str, float]:
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    return {
        "total_GiB": usage.total / 1024**3,
        "used_GiB": usage.used / 1024**3,
        "free_GiB": usage.free / 1024**3,
    }


def _writable(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / f".doctor-write-{os.getpid()}"
    try:
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("ok\n")
            handle.flush()
            os.fsync(handle.fileno())
        return probe.read_text(encoding="utf-8") == "ok\n"
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass


def _version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _givernylocal_runtime_check() -> tuple[bool, str | None]:
    try:
        from givernylocal.turbulence_dataset import turb_dataset  # noqa: F401
        from givernylocal.turbulence_toolkit import getCutout  # noqa: F401
    except (ImportError, OSError) as exc:
        return False, str(exc)
    return True, None


def doctor(cfg: PipelineConfig, time_index: int | None = None) -> dict[str, Any]:
    packages = {
        name: _version(name)
        for name in ("givernylocal", "numpy", "scipy", "zarr", "streamlit")
    }
    runtime_ok, runtime_error = _givernylocal_runtime_check()
    checks = {
        "state_writable": _writable(cfg.state_root),
        "run_writable": _writable(cfg.run_root),
        "result_writable": _writable(cfg.result_root),
        "token_configured": token_source(cfg) is not None,
        "givernylocal_available": packages["givernylocal"] is not None,
        "givernylocal_runtime": runtime_ok,
    }
    payload: dict[str, Any] = {
        "checks": checks,
        "paths": {
            "state_root": str(cfg.state_root),
            "run_root": str(cfg.run_root),
            "result_root": str(cfg.result_root),
        },
        "volumes": {
            "state": _space(cfg.state_root),
            "run": {
                **_space(cfg.run_root),
                "safety_reserve_GiB": cfg.scratch_safety_reserve_gib,
            },
            "result": {
                **_space(cfg.result_root),
                "safety_reserve_GiB": cfg.persistent_safety_reserve_gib,
            },
        },
        "token_source": token_source(cfg),
        "packages": packages,
        "givernylocal_runtime_error": runtime_error,
    }
    if time_index is not None:
        record_path = cfg.run_path(time_index) / "run.json"
        payload["run"] = (
            json.loads(record_path.read_text(encoding="utf-8"))
            if record_path.exists()
            else {"time_index": time_index, "status": "not_created"}
        )
    payload["status"] = "ok" if all(checks.values()) else "failed"
    return payload
