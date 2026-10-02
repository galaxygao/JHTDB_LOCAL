"""Resumable scalar-pressure cutouts and chunked periodic fourth-order derivatives."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time

import numpy as np
import zarr
from filelock import FileLock

from .auth import get_token
from .config import load_config
from .jhtdb import LocalJHTDB
from .planning import requests_for
from .store import array_sha256, compressor, spatial_slices
from .validation import atomic_json


class PressureConfig:
    variable = "pressure"

    def __init__(self, base):
        self.base = base

    def __getattr__(self, key):
        return getattr(self.base, key)


class PressureClient(LocalJHTDB):
    def fetch_tile(self, tile, time_index):
        result = self._get_cutout(self.cube, "pressure",
            np.asarray([*tile.api_ranges, (time_index, time_index)], dtype=np.int32),
            np.ones(4, dtype=np.int32), verbose=False)
        try:
            names = list(result.data_vars)
            if len(names) != 1:
                raise ValueError("Expected one scalar pressure field")
            values = np.asarray(result[names[0]].values)
            if values.shape != (tile.nz, tile.ny, tile.nx, 1):
                raise ValueError(f"Unexpected pressure shape: {values.shape}")
            return np.ascontiguousarray(values[..., 0], dtype="<f4")
        finally:
            result.close()


def identity(cfg, frame):
    return dict(dataset=cfg.dataset, time_index=frame, physical_time=cfg.physical_time(frame),
                grid_shape_xyz=list(cfg.grid_shape), domain_length=cfg.domain_length)


def manifest(path, expected):
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["identity"] != expected:
            raise ValueError(f"Cache provenance mismatch: {path}")
        return data
    return {"identity": expected, "checksums": {}, "status": "partial"}


def download_pressure(cfg, frame, client_factory=PressureClient):
    folder = cfg.persistent_input_path(frame)
    folder.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(folder).free < (4 * np.prod(cfg.grid_shape) + cfg.persistent_safety_reserve_gib * 1024**3):
        raise RuntimeError("Insufficient disk space for scalar pressure and safety reserve")
    expected = {**identity(cfg, frame), "source": "JHTDB getCutout", "variable": "pressure",
                "request_shape_xyz": list(cfg.request_shape)}
    record = folder / "pressure_manifest.json"
    state = manifest(record, expected)
    root = zarr.open_group(str(folder / "pressure_cache.zarr"), mode="a")
    if root.attrs and any(root.attrs.get(k) != v for k, v in expected.items()):
        raise ValueError("Pressure store metadata mismatch")
    root.attrs.update({**expected, "status": "fetching", "axis_order": ["z", "y", "x"],
                       "pressure_definition": "JHTDB kinematic pressure P=p/rho"})
    array = root.require_dataset("pressure", shape=cfg.full_shape_zyx,
        chunks=tuple(reversed(cfg.tile_shape)), dtype="<f4", fill_value=np.nan, compressor=compressor(cfg))
    state["status"] = "partial"
    atomic_json(record, state)
    client = None
    token = None
    blocks = requests_for(cfg)
    for number, tile in enumerate(blocks, 1):
        key = tile.store_slices[1:]
        digest = state["checksums"].get(tile.key)
        if digest and array_sha256(array[key]) == digest:
            print(f"Pressure {number}/{len(blocks)}: verified cache", flush=True)
            continue
        if client is None:
            token = get_token(cfg)
            client = client_factory(PressureConfig(cfg), token, frame)
        for attempt in range(cfg.retries):
            try:
                values = client.fetch_tile(tile, frame)
                if values.shape != (tile.nz, tile.ny, tile.nx) or not np.isfinite(values).all():
                    raise ValueError("Invalid pressure response")
                array[key] = values
                digest = array_sha256(np.asarray(values, dtype="<f4"))
                if array_sha256(array[key]) != digest:
                    raise IOError("Pressure write/read checksum mismatch")
                state["checksums"][tile.key] = digest
                atomic_json(record, state)
                break
            except Exception as exc:
                print(f"Pressure block {number} attempt {attempt+1}: {str(exc).replace(token, '<redacted>')}", flush=True)
                if attempt + 1 == cfg.retries:
                    raise RuntimeError("Pressure download failed; verified blocks retained") from None
                time.sleep(cfg.backoff_seconds * (attempt + 1))
        print(f"Pressure {number}/{len(blocks)}: downloaded and verified", flush=True)
        time.sleep(cfg.request_cooldown_seconds)
    state["status"] = "validated"
    digest = atomic_json(record, state)
    root.attrs.update(status="validated", manifest_hash=digest)
    return folder / "pressure_cache.zarr"


def fd4_block(pressure, slices, lengths_xyz):
    """Two-cell halo wraps the FULL periodic grid, including across chunk seams."""
    indices = [(np.arange(s.start - 2, s.stop + 2) % n) for s, n in zip(slices, pressure.shape)]
    halo = np.asarray(pressure.oindex[tuple(indices)] if hasattr(pressure, "oindex")
                      else pressure[np.ix_(*indices)], dtype=np.float64)
    shape = tuple(s.stop - s.start for s in slices)
    result = np.empty((3, *shape), dtype="<f4")
    for component, axis in enumerate((2, 1, 0)):
        derivative = np.zeros(shape, dtype=np.float64)
        for offset, weight in ((-2, 1), (-1, -8), (1, 8), (2, -1)):
            key = [slice(2, n+2) for n in shape]
            key[axis] = slice(2+offset, 2+offset+shape[axis])
            derivative += weight * halo[tuple(key)]
        result[component] = derivative / (12 * lengths_xyz[component] / pressure.shape[axis])
    return result


def required_pressure_blocks(cfg, slices):
    """All published request blocks intersecting this block's periodic halo."""
    from itertools import product
    origins = []
    for part, n, width in zip(reversed(slices), cfg.grid_shape, cfg.request_shape):
        indices = np.arange(part.start - 2, part.stop + 2) % n
        origins.append(sorted(set((indices // width * width).tolist())))
    return {f"x{x:04d}_y{y:04d}_z{z:04d}" for x, y, z in product(*origins)}


def compute_gradient(cfg, frame, block_size=64, *, follow=False, stop_event=None):
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    with FileLock(str(cfg.lock_path / f"pressure-fd4-{frame}.lock"), timeout=-1):
        return _compute_gradient(cfg, frame, block_size, follow=follow, stop_event=stop_event)


def _compute_gradient(cfg, frame, block_size, *, follow, stop_event):
    if block_size < 1:
        raise ValueError("block_size must be positive")
    folder = cfg.persistent_input_path(frame)
    source_record = folder / "pressure_manifest.json"
    last_change = time.monotonic()
    while not source_record.exists():
        if not follow:
            raise ValueError("Pressure input is missing")
        if (stop_event is not None and stop_event.is_set()) or time.monotonic()-last_change > 1800:
            raise RuntimeError("Pressure download stopped or timed out")
        time.sleep(2)
    source = zarr.open_group(str(folder / "pressure_cache.zarr"), mode="r")
    if any(source.attrs.get(k) != v for k, v in identity(cfg, frame).items()):
        raise ValueError("Pressure frame metadata differs")
    pressure = source["pressure"]
    if shutil.disk_usage(folder).free < (12 * np.prod(cfg.grid_shape) + cfg.persistent_safety_reserve_gib * 1024**3):
        raise RuntimeError("Insufficient disk space for pressure gradient and safety reserve")
    chunks = tuple(min(block_size, n) for n in pressure.shape)
    expected = {**identity(cfg, frame), "source": "local periodic fd4", "method_version": 2,
                "request_shape_xyz": list(cfg.request_shape), "chunks_zyx": list(chunks)}
    record = folder / "pressure_gradient_fd4_manifest.json"
    progress = manifest(record, expected)
    progress["status"] = "partial"
    progress.setdefault("dependencies", {})
    path = folder / "pressure_gradient_fd4_cache.zarr"
    root = zarr.open_group(str(path), mode="a")
    if root.attrs and any(root.attrs.get(k) != v for k, v in expected.items()):
        raise ValueError("Gradient provenance mismatch")
    root.attrs.update({**expected, "status": "computing", "axis_order": ["component", "z", "y", "x"],
                       "components": ["dPdx", "dPdy", "dPdz"], "periodic": [True]*3,
                       "formula": "(P[i-2]-8P[i-1]+8P[i+1]-P[i+2])/(12*h)"})
    array = root.require_dataset("pressure_gradient", shape=(3, *pressure.shape),
        chunks=(3, *chunks), dtype="<f4", fill_value=np.nan, compressor=compressor(cfg))
    blocks = [(s, required_pressure_blocks(cfg, s)) for s in spatial_slices(pressure.shape, chunks)]
    requests = {t.key: t for t in requests_for(cfg)}
    checked_sources, checked_outputs = {}, {}
    previous_count = -1
    while True:
        state = json.loads(source_record.read_text(encoding="utf-8"))
        published = state["checksums"]
        if published != checked_sources:
            last_change = time.monotonic()
        for name, digest in published.items():
            if checked_sources.get(name) != digest:
                if name not in requests or array_sha256(pressure[requests[name].store_slices[1:]]) != digest:
                    raise ValueError(f"Pressure source checksum mismatch: {name}")
                checked_sources[name] = digest
        completed = 0
        for slices, needed in blocks:
            if not needed.issubset(published):
                continue
            name = ",".join(str(s.start) for s in slices)
            dependencies = {key: published[key] for key in sorted(needed)}
            signature = hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode()).hexdigest()
            key = (slice(None), *slices)
            if checked_outputs.get(name) != signature:
                digest = progress["checksums"].get(name)
                if (progress["dependencies"].get(name) != signature or not digest
                        or array_sha256(array[key]) != digest):
                    values = fd4_block(pressure, slices, [cfg.domain_length]*3)
                    if not np.isfinite(values).all():
                        raise ValueError("Non-finite pressure gradient")
                    array[key] = values
                    digest = array_sha256(values)
                    if array_sha256(array[key]) != digest:
                        raise IOError("Gradient write/read checksum mismatch")
                    progress["checksums"][name] = digest
                    progress["dependencies"][name] = signature
                    atomic_json(record, progress)
                checked_outputs[name] = signature
            completed += 1
        if completed != previous_count:
            print(f"Periodic FD4 gradient {completed}/{len(blocks)}: verified; pressure {len(published)}/{len(requests)}", flush=True)
            previous_count = completed
        # Refresh attrs: the downloader may have finalized after this reader opened.
        attrs = zarr.open_group(str(folder / "pressure_cache.zarr"), mode="r").attrs
        if completed == len(blocks) and state["status"] == "validated" and attrs.get("status") == "validated":
            encoded = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
            source_hash = hashlib.sha256(encoded).hexdigest()
            if source_hash != attrs.get("manifest_hash"):
                raise ValueError("Pressure manifest hash mismatch")
            progress.update(status="validated", pressure_manifest_hash=source_hash)
            digest = atomic_json(record, progress)
            root.attrs.update(status="validated", manifest_hash=digest, pressure_manifest_hash=source_hash)
            return path
        if not follow:
            raise ValueError("Pressure input is not fully validated; use --stage follow while downloading")
        if (stop_event is not None and stop_event.is_set()) or time.monotonic()-last_change > 1800:
            raise RuntimeError("Pressure download stopped or made no progress for 30 minutes; partial gradients retained")
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--time-index", required=True, type=int)
    parser.add_argument("--stage", choices=("download", "gradient", "follow", "all"), default="all")
    parser.add_argument("--block-size", type=int, default=64)
    args = parser.parse_args()
    cfg = load_config(args.config)
    cfg.physical_time(args.time_index)
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    if args.stage in ("gradient", "follow"):
        print(compute_gradient(cfg, args.time_index, args.block_size, follow=args.stage == "follow"), flush=True)
        return
    with FileLock(str(cfg.lock_path / "jhtdb-request.lock"), timeout=0):
        if args.stage == "download":
            print(download_pressure(cfg, args.time_index), flush=True)
        else:
            from concurrent.futures import ThreadPoolExecutor
            from threading import Event
            stop = Event()
            with ThreadPoolExecutor(max_workers=1) as executor:
                worker = executor.submit(compute_gradient, cfg, args.time_index, args.block_size,
                                         follow=True, stop_event=stop)
                try:
                    print(download_pressure(cfg, args.time_index), flush=True)
                    print(worker.result(), flush=True)
                finally:
                    stop.set()


if __name__ == "__main__":
    main()
