from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from filelock import FileLock

from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .cq import compute_cq, write_cq_artifacts
from .processing import (
    _finalize_shared_gradient,
    _shared_references,
    _shared_result_is_current,
    _source_key,
    _spatial_keys,
)
from .store import create_shared_center_group, hash_zarr_array, spatial_slices
from .validation import atomic_json, input_manifest_hash
from .weak_asymmetry import write_weak_asymmetry_artifacts


_REGIME_STAGING = "_regime_v6_staging"
_REGIME_BACKUP = "_regime_v5_backup"
_ATTRS_BACKUP = ".zattrs.v5-migration-backup.json"
_FILE_BACKUPS = {
    "manifest.json": ".manifest.v5-migration-backup.json",
    "qa.json": ".qa.v5-migration-backup.json",
    "cq.json": ".cq.v5-migration-backup.json",
    "cq.html": ".cq.v5-migration-backup.html",
    "weak_asymmetry.json": ".weak.v5-migration-backup.json",
    "weak_asymmetry.html": ".weak.v5-migration-backup.html",
    "COMPLETE": ".COMPLETE.v5-migration-backup",
}


def _recover_migration(result_dir: Path, sigma: float) -> None:
    zarr_path = result_dir / result_zarr_name(sigma)
    if not zarr_path.is_dir():
        return
    root = zarr.open_group(str(zarr_path), mode="a")
    attrs_backup = result_dir / _ATTRS_BACKUP
    backups_exist = attrs_backup.is_file() or any(
        (result_dir / backup).is_file() for backup in _FILE_BACKUPS.values()
    ) or _REGIME_BACKUP in root
    if not backups_exist:
        return

    committed = (
        (result_dir / "COMPLETE").is_file()
        and int(root.attrs.get("result_schema_version", 0))
        == RESULT_SCHEMA_VERSION
        and "regime" in root
        and tuple(root["regime"].shape) == tuple(root["work_full"].shape)
    )
    if not committed:
        if _REGIME_BACKUP in root:
            if "regime" in root:
                del root["regime"]
            root.move(_REGIME_BACKUP, "regime")
        if _REGIME_STAGING in root:
            del root[_REGIME_STAGING]
        if attrs_backup.is_file():
            attrs = json.loads(attrs_backup.read_text(encoding="utf-8"))
            root.attrs.clear()
            root.attrs.update(attrs)
        for original, backup in _FILE_BACKUPS.items():
            backup_path = result_dir / backup
            if backup_path.is_file():
                os.replace(backup_path, result_dir / original)

    for name in (_REGIME_STAGING, _REGIME_BACKUP):
        if name in root:
            del root[name]
    attrs_backup.unlink(missing_ok=True)
    for backup in _FILE_BACKUPS.values():
        (result_dir / backup).unlink(missing_ok=True)


def _schema(result_dir: Path, sigma: float) -> int | None:
    if not (result_dir / "COMPLETE").is_file():
        return None
    path = result_dir / result_zarr_name(sigma)
    if not path.is_dir():
        return None
    try:
        root = zarr.open_group(str(path), mode="r")
        return int(root.attrs.get("result_schema_version"))
    except Exception:
        return None


def _promote_velocity_cache(cfg: PipelineConfig, time_index: int) -> Path:
    persistent = cfg.persistent_raw_store_path(time_index)
    legacy = cfg.legacy_raw_store_path(time_index)
    if persistent.is_dir():
        return persistent
    if not legacy.is_dir():
        raise RuntimeError("validated velocity_cache.zarr is missing")
    persistent.parent.mkdir(parents=True, exist_ok=True)
    os.replace(legacy, persistent)
    return persistent


def _verify_velocity_crop(
    cfg: PipelineConfig, raw: Any, stored: Any
) -> None:
    expected = (3, *cfg.result_shape_zyx)
    if tuple(stored.shape) != expected:
        raise RuntimeError("legacy center velocity has an unexpected shape")
    chunks = tuple(int(value) for value in stored.chunks[-3:])
    for component in range(3):
        for relative in _spatial_keys(cfg.result_shape_zyx, chunks):
            legacy = np.asarray(stored[(component,) + relative], dtype=np.float32)
            shared = np.asarray(
                raw[(component,) + _source_key(cfg, relative)], dtype=np.float32
            )
            if not np.array_equal(legacy, shared):
                raise RuntimeError(
                    "legacy center velocity differs from the validated full cache"
                )


def _copy_shared_gradient(
    cfg: PipelineConfig,
    time_index: int,
    manifest_hash: str,
    legacy_gradient: Any,
) -> None:
    expected = (3, 3, *cfg.result_shape_zyx)
    if tuple(legacy_gradient.shape) != expected:
        raise RuntimeError("legacy center gradient has an unexpected shape")
    if _shared_result_is_current(cfg, time_index, manifest_hash):
        shared = zarr.open_group(
            str(cfg.shared_center_store_path(time_index)), mode="r"
        )["gradient"]
        for key in spatial_slices(expected, tuple(legacy_gradient.chunks)):
            if not np.array_equal(legacy_gradient[key], shared[key]):
                raise RuntimeError(
                    "completed sigma results contain different raw gradients"
                )
        return

    staging = cfg.shared_staging_result_path(time_index)
    if staging.exists():
        shutil.rmtree(staging)
    shared_root = create_shared_center_group(
        cfg, time_index, staging=True, overwrite=True
    )
    shared_root.attrs["input_manifest_hash"] = manifest_hash
    destination = shared_root["gradient"]
    for key in spatial_slices(expected, tuple(destination.chunks)):
        values = np.asarray(legacy_gradient[key], dtype="<f4")
        if not np.all(np.isfinite(values)):
            raise ValueError("legacy center gradient contains NaN or Inf")
        destination[key] = values
        if not np.array_equal(values, destination[key]):
            raise IOError("shared gradient failed write/read verification")
    _finalize_shared_gradient(
        cfg, time_index, manifest_hash, shared_root
    )


def _six_code_from_v5(
    old: np.ndarray, full: np.ndarray, resolved: np.ndarray
) -> np.ndarray:
    codes = np.zeros(old.shape, dtype=np.uint8)
    delta_nonnegative = (full - resolved) >= 0.0
    codes[(old == 1) & delta_nonnegative] = 1
    codes[(old == 1) & ~delta_nonnegative] = 2
    codes[old == 2] = 3
    codes[old == 3] = 4
    codes[(old == 4) & delta_nonnegative] = 5
    codes[(old == 4) & ~delta_nonnegative] = 6
    return codes


def _legacy_code_from_v6(codes: np.ndarray) -> np.ndarray:
    legacy = np.zeros(codes.shape, dtype=np.uint8)
    legacy[(codes == 1) | (codes == 2)] = 1
    legacy[codes == 3] = 2
    legacy[codes == 4] = 3
    legacy[(codes == 5) | (codes == 6)] = 4
    return legacy


def _stage_v6_regime(root: Any) -> tuple[Any, dict[str, float]]:
    old = root["regime"]
    work_full = root["work_full"]
    work_resolved = root["work_resolved"]
    expected = tuple(int(value) for value in work_full.shape)
    if tuple(old.shape) != expected or tuple(work_resolved.shape) != expected:
        raise RuntimeError("v5 regime migration requires full-domain work fields")
    if _REGIME_STAGING in root:
        del root[_REGIME_STAGING]
    staged = root.create_dataset(
        _REGIME_STAGING,
        shape=expected,
        chunks=old.chunks,
        dtype="u1",
        compressor=old.compressor,
        fill_value=0,
    )
    occupancy = np.zeros(7, dtype=np.int64)
    point_count = 0
    for key in spatial_slices(expected, tuple(old.chunks)):
        old_values = np.asarray(old[key], dtype=np.uint8)
        full = np.asarray(work_full[key], dtype=np.float32)
        resolved = np.asarray(work_resolved[key], dtype=np.float32)
        if not np.all(np.isfinite(full)) or not np.all(np.isfinite(resolved)):
            raise ValueError("work fields contain NaN or Inf")
        if np.any(old_values > 4):
            raise RuntimeError("source regime is not schema v5")
        values = _six_code_from_v5(old_values, full, resolved)
        if not np.array_equal(_legacy_code_from_v6(values), old_values):
            raise RuntimeError("six-regime aggregation does not reproduce v5")
        staged[key] = values
        occupancy += np.bincount(values.ravel(), minlength=7)
        point_count += values.size
    labels = ("uncertain", "1+", "1-", "2", "3", "4+", "4-")
    return staged, {
        label: float(count / point_count)
        for label, count in zip(labels, occupancy)
    }


def _update_complete_metadata(
    cfg: PipelineConfig,
    time_index: int,
    sigma: float,
    result_dir: Path,
    root: Any,
    regime_field: dict[str, Any],
    occupancy: dict[str, float],
) -> None:
    qa_path = result_dir / "qa.json"
    manifest_path = result_dir / "manifest.json"
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    report = compute_cq(root, cfg)
    cq_hash = write_cq_artifacts(result_dir, report)
    weak_report = report["weak_asymmetry"]
    weak_hash = write_weak_asymmetry_artifacts(result_dir, weak_report)

    qa.update(
        {
            "occupancy": occupancy,
            "regime_encoding": [
                "uncertain", "1+", "1-", "2", "3", "4+", "4-"
            ],
            "cq": {
                "passed": report["passed"],
                "scope": report["scope"],
                "report_version": report["report_version"],
                "report_hash": cq_hash,
                "partition_check": report["partition_check"],
            },
            "weak_asymmetry": {
                "passed": weak_report["passed"],
                "scope": weak_report["scope"],
                "report_version": weak_report["report_version"],
                "report_hash": weak_hash,
                "asymmetry_index": weak_report["global"]["asymmetry_index"],
                "ratio_p99": weak_report["global"]["ratio_p99"],
                "ratio_max": weak_report["global"]["ratio_max"],
                "closure": weak_report["closure"],
            },
        }
    )
    reuse = dict(qa.get("reuse", {}))
    reuse.update(
        {
            "velocity": "shared_full_velocity_crop",
            "gradient": "shared_center_gradient",
            "regime": "persistent_schema_v5_work_fields",
        }
    )
    qa["reuse"] = reuse
    atomic_json(qa_path, qa)

    fields = dict(manifest.get("fields", {}))
    fields["regime"] = regime_field
    scopes = dict(manifest.get("field_scopes", {}))
    scopes.update(
        {
            "velocity": "shared_center_crop",
            "gradient": "shared_center_crop",
            "regime": "full_domain",
        }
    )
    shared_manifest = json.loads(
        (cfg.shared_result_path(time_index) / "shared_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    manifest.update(
        {
            "schema_version": RESULT_SCHEMA_VERSION,
            "algorithm": "full_periodic_spectral_pi_sbar_regime_v6",
            "field_scopes": scopes,
            "fields": fields,
            "shared_fields": {
                "velocity": _shared_references(cfg, time_index, manifest["input_manifest_hash"])[
                    "velocity_store"
                ],
                "gradient": shared_manifest["fields"]["gradient"],
            },
            "regime_encoding": [
                "uncertain", "1+", "1-", "2", "3", "4+", "4-"
            ],
            "cq_passed": report["passed"],
            "cq_report_version": report["report_version"],
            "cq_report_hash": cq_hash,
            "weak_asymmetry_passed": weak_report["passed"],
            "weak_asymmetry_report_version": weak_report["report_version"],
            "weak_asymmetry_report_hash": weak_hash,
        }
    )
    manifest_hash = atomic_json(manifest_path, manifest)
    output_hashes = dict(root.attrs.get("output_hashes", {}))
    output_hashes["regime"] = regime_field["sha256"]
    root.attrs.update(
        {
            "status": "complete",
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "algorithm": "full_periodic_spectral_pi_sbar_regime_v6",
            "field_scopes": scopes,
            "regime_encoding": [
                "uncertain", "1+", "1-", "2", "3", "4+", "4-"
            ],
            "occupancy": occupancy,
            "cq_passed": report["passed"],
            "cq_report_version": report["report_version"],
            "cq_report_hash": cq_hash,
            "weak_asymmetry_passed": weak_report["passed"],
            "weak_asymmetry_report_version": weak_report["report_version"],
            "weak_asymmetry_report_hash": weak_hash,
            "output_hashes": output_hashes,
            "manifest_hash": manifest_hash,
        }
    )
    atomic_json(result_dir / "COMPLETE", {"manifest_hash": manifest_hash})


def _reclaim_redundant(result_dir: Path, sigma: float) -> int:
    root = zarr.open_group(str(result_dir / result_zarr_name(sigma)), mode="a")
    references = result_dir / "shared_refs.json"
    if not references.is_file():
        raise RuntimeError("shared references are required before reclaim")
    payload = json.loads(references.read_text(encoding="utf-8"))
    if not Path(payload["shared_complete"]).is_file():
        raise RuntimeError("shared result is incomplete")
    released = 0
    manifest_path = result_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fields = dict(manifest.get("fields", {}))
    output_hashes = dict(root.attrs.get("output_hashes", {}))
    for name in ("velocity", "gradient"):
        if name in root:
            field = fields.get(name, {})
            released += int(field.get("byte_count", 0))
            del root[name]
        fields.pop(name, None)
        output_hashes.pop(name, None)
    manifest["fields"] = fields
    manifest["redundant_fields_reclaimed"] = True
    manifest_hash = atomic_json(manifest_path, manifest)
    root.attrs.update(
        {
            "output_hashes": output_hashes,
            "manifest_hash": manifest_hash,
            "redundant_fields_reclaimed": True,
        }
    )
    atomic_json(result_dir / "COMPLETE", {"manifest_hash": manifest_hash})
    return released


def _migrate_locked(
    cfg: PipelineConfig,
    time_index: int,
    sigma: float,
    *,
    reclaim_redundant: bool,
) -> dict[str, Any]:
    result_dir = cfg.result_path(time_index, sigma)
    _recover_migration(result_dir, sigma)
    schema = _schema(result_dir, sigma)
    if schema == RESULT_SCHEMA_VERSION:
        released = _reclaim_redundant(result_dir, sigma) if reclaim_redundant else 0
        return {"path": str(result_dir), "status": "already_v6", "released_bytes": released}
    if schema != 5:
        raise RuntimeError("migration requires a complete schema-v5 result")

    manifest_hash = input_manifest_hash(cfg, time_index)
    raw_path = _promote_velocity_cache(cfg, time_index)
    raw_root = zarr.open_group(str(raw_path), mode="r")
    if raw_root.attrs.get("manifest_hash") != manifest_hash:
        raise RuntimeError("velocity cache and input manifest disagree")

    zarr_path = result_dir / result_zarr_name(sigma)
    root = zarr.open_group(str(zarr_path), mode="a")
    for name in (
        "velocity", "gradient", "velocity_bar", "gradient_bar",
        "work_full", "work_resolved", "pi", "s_bar", "regime",
    ):
        if name not in root:
            raise RuntimeError(f"schema-v5 result field is missing: {name}")
    _verify_velocity_crop(cfg, raw_root["velocity"], root["velocity"])
    _copy_shared_gradient(cfg, time_index, manifest_hash, root["gradient"])
    atomic_json(
        result_dir / "shared_refs.json",
        _shared_references(cfg, time_index, manifest_hash),
    )

    staged, occupancy = _stage_v6_regime(root)
    digest, byte_count, minimum, maximum = hash_zarr_array(staged)
    regime_field = {
        "shape": list(staged.shape),
        "dtype": str(np.dtype(staged.dtype)),
        "chunks": list(staged.chunks),
        "sha256": digest,
        "byte_count": byte_count,
        "minimum": minimum,
        "maximum": maximum,
    }
    if _REGIME_BACKUP in root:
        del root[_REGIME_BACKUP]
    atomic_json(result_dir / _ATTRS_BACKUP, dict(root.attrs))
    for original, backup in _FILE_BACKUPS.items():
        source = result_dir / original
        destination = result_dir / backup
        if destination.exists():
            destination.unlink()
        if original == "COMPLETE":
            os.replace(source, destination)
        elif source.is_file():
            shutil.copy2(source, destination)
    root.move("regime", _REGIME_BACKUP)
    root.move(_REGIME_STAGING, "regime")
    try:
        _update_complete_metadata(
            cfg, time_index, sigma, result_dir, root, regime_field, occupancy
        )
    except Exception:
        _recover_migration(result_dir, sigma)
        raise
    _recover_migration(result_dir, sigma)

    released = _reclaim_redundant(result_dir, sigma) if reclaim_redundant else 0
    return {
        "path": str(result_dir),
        "status": "migrated_v5_to_v6",
        "released_bytes": released,
        "occupancy": occupancy,
    }


def migrate_existing_result(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float | None = None,
    *,
    reclaim_redundant: bool = False,
) -> dict[str, Any]:
    sigma = cfg.sigma_grid if sigma_grid is None else float(sigma_grid)
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    with FileLock(str(cfg.lock_path / "process-center.lock"), timeout=0):
        return _migrate_locked(
            cfg,
            time_index,
            sigma,
            reclaim_redundant=reclaim_redundant,
        )
