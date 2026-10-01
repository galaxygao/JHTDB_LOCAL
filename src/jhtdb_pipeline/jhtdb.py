from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
from filelock import FileLock
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from .auth import get_token
from .catalog import Catalog
from .config import PipelineConfig
from .doctor import ensure_run_record
from .planning import Tile, requests_for, tiles_for, tiles_in_request
from .store import VelocityStore, array_sha256


class LocalJHTDB:
    """Strictly serial wrapper around the official local Giverny client."""

    def __init__(self, cfg: PipelineConfig, token: str, time_index: int):
        try:
            from givernylocal.turbulence_dataset import turb_dataset
            from givernylocal.turbulence_toolkit import getCutout, getData
        except ImportError as exc:
            raise RuntimeError(
                "The local Giverny runtime cannot be imported; install this project "
                "with givernylocal>=3.6.2. "
                f"Underlying import error: {exc}"
            ) from exc
        output = cfg.run_path(time_index) / "giverny"
        output.mkdir(parents=True, exist_ok=True)
        self.cfg = cfg
        self.token = token
        self.cube = turb_dataset(cfg.dataset, str(output), token)
        self._get_cutout = getCutout
        self._get_data = getData
        self._max_data_points = int(self.cube.metadata["constants"]["max_data_points"])

    def fetch_tile(self, tile: Tile, time_index: int) -> np.ndarray:
        if self.cfg.variable == "pressure_gradient":
            return self.fetch_pressure_gradient(tile, time_index)
        xyzt_ranges = np.asarray(
            [*tile.api_ranges, (time_index, time_index)], dtype=np.int32
        )
        strides = np.ones(4, dtype=np.int32)
        result = self._get_cutout(
            self.cube,
            self.cfg.variable,
            xyzt_ranges,
            strides,
            verbose=False,
        )
        try:
            names = list(result.data_vars)
            if len(names) != 1:
                raise RuntimeError(f"expected one velocity variable, got {names}")
            return canonicalize_cutout(np.asarray(result[names[0]].values), tile)
        finally:
            close = getattr(result, "close", None)
            if callable(close):
                close()


    def fetch_pressure_gradient(self, tile: Tile, time_index: int) -> np.ndarray:
        """Query server derivatives at the exact velocity grid locations."""
        count = tile.nx * tile.ny * tile.nz
        if count > self._max_data_points:
            raise ValueError(f"pressure request has {count} points; server limit is {self._max_data_points}")
        spacing = self.cfg.domain_length / np.asarray(self.cfg.grid_shape)
        z, y, x = np.unravel_index(np.arange(count), (tile.nz, tile.ny, tile.nx))
        points = np.column_stack((x + tile.x0, y + tile.y0, z + tile.z0)) * spacing
        result = self._get_data(
            self.cube, "pressure", self.cfg.physical_time(time_index),
            "none", "fd4noint", "gradient", points, verbose=False,
        )
        if len(result) != 1:
            raise RuntimeError("expected exactly one pressure-gradient time frame")
        values = np.asarray(result[0], dtype="<f4")
        if values.shape != (count, 3) or not np.isfinite(values).all():
            raise RuntimeError("invalid pressure-gradient response shape or non-finite values")
        return canonicalize_cutout(values.reshape(tile.nz, tile.ny, tile.nx, 3), tile)


def canonicalize_cutout(values: np.ndarray, tile: Tile) -> np.ndarray:
    """Convert Giverny ``(z,y,x,component)`` to ``(component,z,y,x)``."""
    expected = (tile.nz, tile.ny, tile.nx, 3)
    if values.shape != expected:
        raise RuntimeError(f"GetCutout shape {values.shape}, expected {expected}")
    canonical = np.ascontiguousarray(np.moveaxis(values, -1, 0), dtype="<f4")
    if not np.all(np.isfinite(canonical)):
        raise RuntimeError("GetCutout returned NaN or Inf")
    return canonical


def chunk_from_request(values: np.ndarray, request: Tile, tile: Tile) -> np.ndarray:
    """Copy one canonical checksum tile from a larger canonical request block."""
    expected_request = (3, request.nz, request.ny, request.nx)
    if values.shape != expected_request:
        raise ValueError(
            f"request array shape {values.shape}, expected {expected_request}"
        )
    relative = (
        slice(None),
        slice(tile.z0 - request.z0, tile.z0 - request.z0 + tile.nz),
        slice(tile.y0 - request.y0, tile.y0 - request.y0 + tile.ny),
        slice(tile.x0 - request.x0, tile.x0 - request.x0 + tile.nx),
    )
    chunk = np.ascontiguousarray(values[relative], dtype="<f4")
    expected_tile = (3, tile.nz, tile.ny, tile.nx)
    if chunk.shape != expected_tile:
        raise ValueError(
            f"tile {tile.key} is not contained in request {request.key}"
        )
    return chunk


def scratch_space(cfg: PipelineConfig, time_index: int) -> dict[str, float]:
    pressure = cfg.variable == "pressure_gradient"
    path = cfg.raw_store_path(time_index).parent if pressure else cfg.run_root
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    reserve = cfg.persistent_safety_reserve_gib if pressure else cfg.scratch_safety_reserve_gib
    required = cfg.bytes_per_snapshot + int(reserve * 1024**3)
    if usage.free < required:
        raise RuntimeError(
            f"insufficient scratch space: {usage.free / 1024**3:.2f} GiB free, "
            f"need {required / 1024**3:.2f} GiB before fetching frame {time_index}"
        )
    return {
        "free_GiB": usage.free / 1024**3,
        "required_GiB": required / 1024**3,
    }


def smoke(cfg: PipelineConfig, time_index: int) -> dict[str, object]:
    token = get_token(cfg)
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    with FileLock(str(cfg.lock_path / "jhtdb-request.lock"), timeout=0):
        values = LocalJHTDB(cfg, token, time_index).fetch_tile(
            Tile(0, 0, 0, 8, 8, 8), time_index
        )
    return {
        "status": "ok",
        "dataset": cfg.dataset,
        "variable": cfg.variable,
        "time_index": time_index,
        "physical_time": cfg.physical_time(time_index),
        "shape": list(values.shape),
        "dtype": str(values.dtype),
        "finite": bool(np.all(np.isfinite(values))),
        "minimum": float(values.min()),
        "maximum": float(values.max()),
    }


def fetch_snapshot(cfg: PipelineConfig, time_index: int) -> Path:
    cfg.physical_time(time_index)
    cfg.state_root.mkdir(parents=True, exist_ok=True)
    cfg.run_path(time_index).mkdir(parents=True, exist_ok=True)
    ensure_run_record(cfg, time_index)
    space = scratch_space(cfg, time_index)
    token = get_token(cfg)
    console = Console()
    console.print(
        f"[bold]JHTDB serial fetch[/bold] frame={time_index} "
        f"free_scratch={space['free_GiB']:.2f} GiB"
    )
    console.print("[yellow]Exactly one JHTDB request is allowed in flight.[/yellow]")

    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(cfg.lock_path / "jhtdb-request.lock"), timeout=0)
    with lock:
        client = LocalJHTDB(cfg, token, time_index)
        tiles = tiles_for(cfg)
        requests = requests_for(cfg)
        # Index once instead of scanning 262144 checksum tiles per request.
        pressure_tiles = {}
        if cfg.variable == "pressure_gradient":
            rx, ry, rz = cfg.request_shape
            for tile in tiles:
                origin = (tile.x0 // rx * rx, tile.y0 // ry * ry, tile.z0 // rz * rz)
                pressure_tiles.setdefault(origin, []).append(tile)
            console.print(f"Pressure gradient: {len(requests)} request blocks, shape_xyz={cfg.request_shape}")
        store = VelocityStore(cfg, time_index)
        store.ensure_array()
        store.root.attrs["status"] = "fetching"
        with Catalog(cfg.catalog_path) as catalog:
            catalog.plan_snapshot(
                cfg.dataset, time_index, cfg.physical_time(time_index), tiles
            )
            catalog.set_snapshot_status(cfg.dataset, time_index, "fetching")
            with Progress(
                SpinnerColumn("line"),
                TextColumn("{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("{task.fields[state]}"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"frame {time_index}", total=len(requests), state="starting"
                )
                for request_number, request in enumerate(requests, start=1):
                    if cfg.variable == "pressure_gradient":
                        request_tiles = pressure_tiles[(request.x0, request.y0, request.z0)]
                    else:
                        request_tiles = [request] if cfg.request_shape == cfg.tile_shape else tiles_in_request(request, tiles)
                    pending: list[Tile] = []
                    for tile in request_tiles:
                        row = catalog.tile(cfg.dataset, time_index, tile.key)
                        if (
                            row is not None
                            and row["status"] == "verified"
                            and row["sha256"]
                        ):
                            readback = np.ascontiguousarray(
                                store.array[tile.store_slices], dtype="<f4"
                            )
                            if array_sha256(readback) == row["sha256"]:
                                continue
                        pending.append(tile)
                    if not pending:
                        progress.update(
                            task,
                            advance=1,
                            state=f"verified request {request_number}/{len(requests)}",
                        )
                        continue
                    last_error: Exception | None = None
                    for attempt in range(1, cfg.retries + 1):
                        for tile in pending:
                            catalog.mark_attempt(cfg.dataset, time_index, tile.key)
                        progress.update(
                            task,
                            state=(
                                f"request {request_number}/{len(requests)} "
                                f"attempt {attempt}/{cfg.retries}"
                            ),
                        )
                        values: np.ndarray | None = None
                        try:
                            values = client.fetch_tile(request, time_index)
                            for tile in pending:
                                chunk = chunk_from_request(values, request, tile)
                                digest = store.write_tile(tile, chunk)
                                catalog.mark_verified(
                                    cfg.dataset,
                                    time_index,
                                    tile.key,
                                    digest,
                                    chunk.nbytes,
                                )
                            last_error = None
                            break
                        except Exception as exc:
                            last_error = exc
                            message = str(exc).replace(token, "<redacted>")
                            console.print(
                                f"[red]request {request.key} failed:[/red] {message}"
                            )
                            if attempt < cfg.retries:
                                time.sleep(cfg.backoff_seconds * attempt)
                        finally:
                            del values
                    if last_error is not None:
                        catalog.set_snapshot_status(cfg.dataset, time_index, "partial")
                        raise RuntimeError(str(last_error).replace(token, "<redacted>")) from None
                    progress.update(
                        task,
                        advance=1,
                        state=f"verified request {request_number}/{len(requests)}",
                    )
                    if cfg.request_cooldown_seconds:
                        time.sleep(cfg.request_cooldown_seconds)

    from .validation import validate_snapshot

    report = validate_snapshot(cfg, time_index)
    console.print(json.dumps(report, ensure_ascii=False, indent=2))
    return cfg.raw_store_path(time_index)
