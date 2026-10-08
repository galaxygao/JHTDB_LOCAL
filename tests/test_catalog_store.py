from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from jhtdb_pipeline.catalog import Catalog
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.planning import Tile
from jhtdb_pipeline.store import VelocityStore, array_sha256, load_chained_report, report_metadata
from jhtdb_pipeline import validation
from jhtdb_pipeline.validation import atomic_json, update_report_metadata, validate_snapshot


def small_config(root: Path):
    return replace(
        load_config("configs/pipeline.yaml"),
        grid_shape=(16, 16, 16),
        request_shape=(8, 8, 8),
        tile_shape=(8, 8, 8),


        state_root=root / "state",
        run_root=root / "runs",
        result_root=root / "results",
        persistent_safety_reserve_gib=0.0,
        scratch_safety_reserve_gib=0.0,
    )


class CatalogStoreTests(unittest.TestCase):
    def test_tile_roundtrip_and_unique_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg = small_config(Path(temporary))
            tile = Tile(0, 0, 0, 8, 8, 8)
            values = np.arange(3 * 8**3, dtype=np.float32).reshape(3, 8, 8, 8)
            store = VelocityStore(cfg, 1)
            store.ensure_array()
            digest = store.write_tile(tile, values)
            self.assertEqual(digest, array_sha256(values))
            np.testing.assert_array_equal(store.array[tile.store_slices], values)
            with Catalog(cfg.catalog_path) as catalog:
                catalog.plan_snapshot(cfg.dataset, 1, 0.0, [tile])
                catalog.plan_snapshot(cfg.dataset, 1, 0.0, [tile])
                self.assertEqual(len(catalog.tiles(cfg.dataset, 1)), 1)
                catalog.mark_verified(cfg.dataset, 1, tile.key, digest, values.nbytes)
                self.assertEqual(
                    catalog.tile_progress(cfg.dataset, 1), {"verified": 1, "total": 1}
                )

    def test_complete_small_snapshot_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg = small_config(Path(temporary))
            tiles = [
                Tile(x, y, z, 8, 8, 8)
                for z in (0, 8)
                for y in (0, 8)
                for x in (0, 8)
            ]
            store = VelocityStore(cfg, 1)
            store.ensure_array()
            with Catalog(cfg.catalog_path) as catalog:
                catalog.plan_snapshot(cfg.dataset, 1, 0.0, tiles)
                for tile in tiles:
                    z, y, x = np.mgrid[
                        tile.z0 : tile.z0 + 8,
                        tile.y0 : tile.y0 + 8,
                        tile.x0 : tile.x0 + 8,
                    ]
                    values = np.stack((x, y, z)).astype(np.float32)
                    digest = store.write_tile(tile, values)
                    catalog.mark_verified(
                        cfg.dataset, 1, tile.key, digest, values.nbytes
                    )
            report = validate_snapshot(cfg, 1)
            self.assertEqual(report["status"], "validated")
            self.assertTrue(report["coverage_exactly_once"])
            reopened = VelocityStore(cfg, 1)
            self.assertEqual(reopened.root.attrs["status"], "validated")


@pytest.mark.parametrize(
    "name,version,html",
    [("s_bar_qa", 1, "s_bar_global_totals.html"),
     ("weak_asymmetry", 2, "weak_asymmetry.html")],
)
def test_qa_report_chain_rejects_tampering_and_incomplete_artifacts(tmp_path, name, version, html):
    report = {"report_version": version, "scope": "full_domain", "passed": False}
    report_path = tmp_path / f"{name}.json"
    report_hash = atomic_json(report_path, report)
    manifest = {f"{name}_report_version": version, f"{name}_report_hash": report_hash}
    manifest_path = tmp_path / "manifest.json"
    manifest_hash = atomic_json(manifest_path, manifest)
    complete_path = tmp_path / "COMPLETE"
    atomic_json(complete_path, {"manifest_hash": manifest_hash})
    (tmp_path / html).write_text("report")
    root = SimpleNamespace(attrs={**manifest, "manifest_hash": manifest_hash})

    def read():
        return load_chained_report(tmp_path, root, name, version, html_name=html)

    # Failed scientific QA still has a valid integrity chain and can be reused.
    assert read() == report
    for path in (report_path, manifest_path, complete_path, tmp_path / html):
        original = path.read_bytes()
        path.unlink()
        assert read() is None
        path.write_bytes(original)
    for path in (report_path, manifest_path, complete_path):
        original = path.read_bytes()
        path.write_text('{}')
        assert read() is None
        path.write_bytes(original)
    root.attrs[f"{name}_report_version"] = version + 1
    assert read() is None
    root.attrs[f"{name}_report_version"] = version
    assert read() == report


@pytest.mark.parametrize("failure", ["manifest.json", "attrs", "COMPLETE"])
def test_interrupted_report_refresh_rejects_stale_chain_and_can_retry(tmp_path, monkeypatch, failure):
    report_path = tmp_path / "weak_asymmetry.json"
    report = {"report_version": 2, "scope": "full_domain", "passed": True}
    metadata = report_metadata("weak_asymmetry", report, atomic_json(report_path, report))
    preserved = {"fields": {"pi": {"sha256": "field-hash"}}, "other_report_hash": "other-hash"}
    manifest_hash = atomic_json(tmp_path / "manifest.json", {**preserved, **metadata})
    atomic_json(tmp_path / "COMPLETE", {"manifest_hash": manifest_hash})
    (tmp_path / "weak_asymmetry.html").write_text("report")

    class FailingAttrs(dict):
        def update(self, values):
            if failure == "attrs":
                raise OSError("interrupted attrs write")
            super().update(values)

    root = SimpleNamespace(attrs=FailingAttrs({**preserved, **metadata, "manifest_hash": manifest_hash}))
    assert load_chained_report(tmp_path, root, "weak_asymmetry", 2) == report
    complete_before = (tmp_path / "COMPLETE").read_bytes()
    # A failed scientific QA is still a valid report when persistence completes.
    report = {**report, "passed": False}
    metadata = report_metadata("weak_asymmetry", report, atomic_json(report_path, report))

    def interrupted_json(path, payload):
        if path.name == failure:
            raise OSError("interrupted JSON write")
        return atomic_json(path, payload)

    with monkeypatch.context() as patcher:
        patcher.setattr(validation, "atomic_json", interrupted_json)
        with pytest.raises(OSError, match="interrupted"):
            update_report_metadata(tmp_path, root, metadata)
    assert (tmp_path / "COMPLETE").read_bytes() == complete_before
    assert load_chained_report(tmp_path, root, "weak_asymmetry", 2) is None

    root.attrs = dict(root.attrs)
    update_report_metadata(tmp_path, root, metadata)
    assert load_chained_report(tmp_path, root, "weak_asymmetry", 2) == report
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    for key, value in preserved.items():
        assert manifest[key] == root.attrs[key] == value


if __name__ == "__main__":
    unittest.main()
