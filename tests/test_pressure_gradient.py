from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
import zarr

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import field_config, open_frame_fields
from jhtdb_pipeline.jhtdb import LocalJHTDB, fetch_snapshot
from jhtdb_pipeline.planning import Tile, requests_for
from jhtdb_pipeline.cli import build_parser


def config(tmp_path):
    return replace(load_config("configs/pipeline.yaml"), grid_shape=(16,16,16),
                   request_shape=(16,16,16), tile_shape=(8,8,8),
                   state_root=tmp_path / "state", run_root=tmp_path / "runs",
                   result_root=tmp_path / "results", scratch_safety_reserve_gib=0,
                   persistent_safety_reserve_gib=0, request_cooldown_seconds=0,
                   retries=1)


def test_server_coordinates_time_and_axis_order(tmp_path):
    cfg = field_config(config(tmp_path), "pressure_gradient")
    client = object.__new__(LocalJHTDB)
    client.cfg, client.cube = cfg, object()
    client._max_data_points = 2_000_000
    calls = []
    def get_data(cube, var, time, temporal, spatial, operator, points, **kwargs):
        calls.append((var, time, temporal, spatial, operator, points.copy()))
        return [points * [1,2,3]]
    client._get_data = get_data
    tile = Tile(2,3,4,3,2,2)
    values = client.fetch_tile(tile, 2)
    assert values.shape == (3,2,2,3)
    assert calls[0][:5] == ("pressure", .002, "none", "fd4noint", "gradient")
    step = cfg.domain_length / 16
    np.testing.assert_allclose(values[:,0,0,0], np.array([2,6,12])*step)
    np.testing.assert_allclose(values[:,1,1,2], np.array([4,8,15])*step)
    client._get_data = lambda *a, **k: [np.full((12,3), np.nan)]
    with pytest.raises(RuntimeError, match="non-finite"):
        client.fetch_tile(tile, 2)


def test_resume_corruption_and_velocity_isolation(tmp_path):
    cfg = config(tmp_path)
    pressure = field_config(cfg, "pressure_gradient")
    class Fake:
        calls = 0
        def fetch_tile(self, tile, time_index):
            self.calls += 1
            return np.full((3,tile.nz,tile.ny,tile.nx), 2, dtype=np.float32)
    fake = Fake()
    with patch("jhtdb_pipeline.jhtdb.get_token", return_value="secret"), patch("jhtdb_pipeline.jhtdb.LocalJHTDB", return_value=fake):
        fetch_snapshot(cfg, 1)
        velocity_manifest = (cfg.manifest_path / "input_t000001.json").read_bytes()
        fetch_snapshot(pressure, 1)
        assert fake.calls == 2
        fetch_snapshot(pressure, 1)
        assert fake.calls == 2
        root = zarr.open_group(str(pressure.raw_store_path(1)), mode="a")
        root["pressure_gradient"][0,0,0,0] = 99
        fetch_snapshot(pressure, 1)
        assert fake.calls == 3
        assert root["pressure_gradient"][0,0,0,0] == 2
    assert (cfg.manifest_path / "input_t000001.json").read_bytes() == velocity_manifest
    fields = open_frame_fields(cfg, 1)
    assert set(fields) == {"velocity", "pressure_gradient"}
    assert root.attrs["spatial_method"] == "fd4noint"
    root.attrs["physical_time"] = 99
    with pytest.raises(ValueError, match="metadata"):
        open_frame_fields(cfg, 1)


def test_cli_field_selection():
    args = build_parser().parse_args(["cache", "--time-index", "1", "--field", "pressure_gradient"])
    assert args.field == "pressure_gradient"
    args = build_parser().parse_args(["single-frame", "--time-index", "1", "--with-pressure-gradient"])
    assert args.with_pressure_gradient


def test_production_request_is_one_server_call(tmp_path):
    cfg = field_config(load_config("configs/pipeline.yaml"), "pressure_gradient")
    assert cfg.request_shape == (128, 128, 64)
    assert cfg.tile_shape == (16, 16, 16)
    assert len(requests_for(cfg)) == 1024
    client = object.__new__(LocalJHTDB)
    client.cfg, client.cube = cfg, object()
    client._max_data_points = 2_000_000
    calls = []
    def get_data(cube, var, time, temporal, spatial, operator, points, **kwargs):
        calls.append(len(points))
        return [points]
    client._get_data = get_data
    tile = Tile(128, 256, 64, 128, 128, 64)
    values = client.fetch_tile(tile, 1)
    assert calls == [1_048_576]
    assert values.shape == (3, 64, 128, 128)
    step = cfg.domain_length / 1024
    np.testing.assert_allclose(values[:, 0, 0, 0], np.array([128, 256, 64]) * step)
    np.testing.assert_allclose(values[:, -1, -1, -1], np.array([255, 383, 127]) * step)
    client._max_data_points = 1_000_000
    with pytest.raises(ValueError, match="server limit"):
        client.fetch_tile(tile, 1)
    assert len(calls) == 1


def test_old_small_request_cache_resumes_with_large_requests(tmp_path):
    cfg = field_config(replace(config(tmp_path), grid_shape=(32,32,32)), "pressure_gradient")
    class Fake:
        calls = []
        def fetch_tile(self, tile, time_index):
            self.calls.append(tile)
            return np.full((3,tile.nz,tile.ny,tile.nx), 2, dtype=np.float32)
    fake = Fake()
    with patch("jhtdb_pipeline.jhtdb.get_token", return_value="private-token"), patch("jhtdb_pipeline.jhtdb.LocalJHTDB", return_value=fake):
        # Simulate a cache produced by the old download implementation.
        cfg.request_shape = cfg.tile_shape
        fetch_snapshot(cfg, 1)
        assert len(fake.calls) == 8
        large = field_config(cfg.base, "pressure_gradient")
        fetch_snapshot(large, 1)
        assert len(fake.calls) == 8
        root = zarr.open_group(str(cfg.raw_store_path(1)), mode="a")
        root["pressure_gradient"][0, 0, 0, 0] = 99
        fetch_snapshot(large, 1)
        assert len(fake.calls) == 9
        assert fake.calls[-1] == Tile(0, 0, 0, 32, 32, 32)
        np.testing.assert_array_equal(root["pressure_gradient"][:], 2)
