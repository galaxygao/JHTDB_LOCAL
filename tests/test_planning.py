from __future__ import annotations

import unittest
import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np
import yaml

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.jhtdb import canonicalize_cutout, chunk_from_request
from jhtdb_pipeline.planning import (
    Tile, coordinate_for_index, plan, requests_for, tiles_for, tiles_in_request,
)
from jhtdb_pipeline.processing import resource_plan


class PlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        # Planning expectations below intentionally exercise the Gaussian
        # result namespace, independent of the production YAML defaults.
        self.cfg = load_config("configs/pipeline.yaml").with_filter("gaussian")

    def test_configuration_rejects_removed_spatial_storage_options(self):
        source = Path("configs/pipeline.macos.yaml").read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pipeline.yaml"
            for section in (None, "storage", "physics"):
                for key in ("crop_start", "crop_shape"):
                    with self.subTest(section=section, key=key):
                        data = yaml.safe_load(source)
                        target = data if section is None else data[section]
                        target[key] = [256, 256, 256]
                        path.write_text(yaml.safe_dump(data))
                        with self.assertRaisesRegex(ValueError, "unknown .* fields"):
                            load_config(path)

    def test_full_domain_is_exactly_512_nonoverlapping_tiles(self):
        tiles = tiles_for(self.cfg)
        self.assertEqual(len(tiles), 512)
        self.assertEqual(len({tile.key for tile in tiles}), 512)
        self.assertEqual(sum(tile.nx * tile.ny * tile.nz for tile in tiles), 1024**3)
        self.assertEqual(tiles[0].api_ranges, ((1, 128), (1, 128), (1, 128)))
        self.assertEqual(tiles[-1].api_ranges, ((897, 1024), (897, 1024), (897, 1024)))

    def test_plan_is_single_time_and_serial(self):
        batch_cfg = replace(
            self.cfg,
            sigma_grid=1.0,
            sigma_grids=(1.0, 2.0, 3.0),
        )
        result = plan(batch_cfg, 3)
        self.assertEqual(result["time_index"], 3)
        self.assertEqual(result["physical_time"], 0.004)
        self.assertTrue(result["strictly_serial"])
        self.assertEqual(result["requests_if_no_retry"], 128)
        self.assertEqual(result["request_uncompressed_GiB"], 0.094)
        self.assertEqual(result["checksum_tiles"], 512)
        self.assertEqual(result["sigma_grids"], [1.0, 2.0, 3.0])
        self.assertEqual(
            [
                path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                for path in result["result_paths"]
            ],
            ["t000003_sigma_1", "t000003_sigma_2", "t000003_sigma_3"],
        )

    def test_each_request_contains_four_checksum_tiles(self):
        tiles = tiles_for(self.cfg)
        requests = requests_for(self.cfg)
        self.assertEqual(len(requests), 128)
        grouped = [tiles_in_request(request, tiles) for request in requests]
        self.assertTrue(all(len(group) == 4 for group in grouped))
        self.assertEqual(
            {tile.key for group in grouped for tile in group},
            {tile.key for tile in tiles},
        )

    def test_local_request_size_is_limited_to_100_mib(self):
        with self.assertRaisesRegex(ValueError, "at most 100 MiB"):
            replace(self.cfg, request_shape=(256, 256, 256)).validate()

    def test_full_domain_energy_fields_are_in_local_capacity_plan(self):
        batch_cfg = replace(
            self.cfg,
            sigma_grid=1.0,
            sigma_grids=(1.0, 2.0, 3.0),
        )
        resources = resource_plan(batch_cfg)
        self.assertEqual(resources["result_GiB"], 23.0)
        self.assertEqual(resources["batch_result_GiB"], 69.0)
        self.assertEqual(resources["shared_gradient_GiB"], 4.5)
        self.assertEqual(resources["batch_persistent_GiB"], 85.5)
        self.assertEqual(resources["batch_with_reserve_GiB"], 109.5)

class CoordinateTests(unittest.TestCase):
    def test_cutout_zyxc_to_component_zyx_mapping(self):
        tile = Tile(x0=10, y0=20, z0=30, nx=4, ny=3, nz=2)
        values = np.empty((2, 3, 4, 3), dtype=np.float32)
        for z in range(2):
            for y in range(3):
                for x in range(4):
                    for component in range(3):
                        values[z, y, x, component] = (
                            1000 * component + 100 * z + 10 * y + x
                        )
        canonical = canonicalize_cutout(values, tile)
        self.assertEqual(canonical.shape, (3, 2, 3, 4))
        for component in range(3):
            for z in range(2):
                for y in range(3):
                    for x in range(4):
                        self.assertEqual(
                            canonical[component, z, y, x],
                            1000 * component + 100 * z + 10 * y + x,
                        )

    def test_large_request_splits_into_exact_checksum_tiles(self):
        request = Tile(128, 256, 384, 8, 8, 8)
        values = np.arange(3 * 8 * 8 * 8, dtype=np.float32).reshape(3, 8, 8, 8)
        rebuilt = np.empty_like(values)
        for z in (384, 388):
            for y in (256, 260):
                for x in (128, 132):
                    tile = Tile(x, y, z, 4, 4, 4)
                    chunk = chunk_from_request(values, request, tile)
                    rebuilt[
                        :,
                        z - request.z0 : z - request.z0 + 4,
                        y - request.y0 : y - request.y0 + 4,
                        x - request.x0 : x - request.x0 + 4,
                    ] = chunk
        np.testing.assert_array_equal(rebuilt, values)

    def test_periodic_coordinates_do_not_duplicate_endpoint(self):
        length = 2.0 * np.pi
        self.assertEqual(coordinate_for_index(0, 1024, length), 0.0)
        self.assertAlmostEqual(
            coordinate_for_index(1023, 1024, length), length - length / 1024
        )
        with self.assertRaises(IndexError):
            coordinate_for_index(1024, 1024, length)

    def test_api_ranges_are_one_based_while_store_is_zero_based(self):
        tile = Tile(x0=128, y0=256, z0=384, nx=128, ny=128, nz=128)
        self.assertEqual(tile.api_ranges, ((129, 256), (257, 384), (385, 512)))
        self.assertEqual(tile.store_slices[3], slice(128, 256))
        self.assertEqual(tile.store_slices[2], slice(256, 384))
        self.assertEqual(tile.store_slices[1], slice(384, 512))

if __name__ == "__main__":
    unittest.main()
