from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import zarr

from jhtdb_pipeline.catalog import Catalog
from jhtdb_pipeline.config import load_config, result_zarr_name
from jhtdb_pipeline.cq import ensure_cq_result
from jhtdb_pipeline.physics import axis2_spectrum as physics_axis2_spectrum
from jhtdb_pipeline.physics import full_spectrum as physics_full_spectrum
from jhtdb_pipeline.physics import spectral_derivative, spectral_gaussian
from jhtdb_pipeline.planning import Tile
from jhtdb_pipeline.sbar_qa import ensure_sbar_result, run_sbar_qa
from jhtdb_pipeline.processing import (
    filter_field as processing_filter_field,
    finalize_result,
    process_batch,
    process_full,
    resource_plan,
)
from jhtdb_pipeline.store import VelocityStore, open_complete_result
from jhtdb_pipeline.validation import atomic_json


def fixture(root: Path, *, compressible: bool = False):
    cfg = replace(
        load_config("configs/pipeline.yaml").with_filter("gaussian"),
        grid_shape=(16, 16, 16),
        request_shape=(16, 16, 16),
        tile_shape=(8, 8, 8),


        state_root=root / "state",
        run_root=root / "runs",
        result_root=root / "results",
        persistent_safety_reserve_gib=0.0,
        scratch_safety_reserve_gib=0.0,
        fft_workers=2,
        fft_slab_width=2,
        cleanup_scratch_on_success=True,
        sigma_grid=2.0,
        sigma_grids=(2.0,),
        sharp_edge_width_fraction=0.1171875,
    )
    coordinates = np.arange(16, dtype=np.float32) * (2.0 * np.pi / 16)
    z, y, x = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    velocity = np.zeros((3, 16, 16, 16), dtype=np.float32)
    if compressible:
        velocity[0] = np.sin(x)
    else:
        velocity[0] = np.sin(x) * np.cos(y)
        velocity[1] = -np.cos(x) * np.sin(y)

    store = VelocityStore(cfg, 1)
    store.ensure_array()
    store.array[:] = velocity
    store.root.attrs.update({"status": "validated", "manifest_hash": "input-hash"})
    with Catalog(cfg.catalog_path) as catalog:
        catalog.plan_snapshot(
            cfg.dataset, 1, 0.0, [Tile(0, 0, 0, 16, 16, 16)]
        )
        catalog.set_snapshot_status(cfg.dataset, 1, "validated", "input-hash")
    return cfg, velocity


class ProcessingTests(unittest.TestCase):
    def test_smooth_sharp_batch_reuses_full_spectra_and_tracks_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            cfg = replace(
                cfg,
                filter_type="smooth_sharp",
                sharp_edge_width_fraction=0.125,
                sigma_grid=2.0,
                sigma_grids=(2.0, 3.0),
            )
            with patch(
                "jhtdb_pipeline.processing.full_spectrum",
                wraps=physics_full_spectrum,
            ) as cached_fft:
                paths = process_batch(cfg, 1, cfg.sigma_grids)
            self.assertEqual(cached_fft.call_count, 12)
            self.assertTrue(all((path / "COMPLETE").is_file() for path in paths))
            batch = json.loads(
                cfg.batch_manifest_path(1).read_text(encoding="utf-8")
            )
            self.assertEqual(batch["status"], "complete")
            self.assertEqual(batch["filter_type"], "smooth_sharp")
            self.assertTrue(all(item["complete"] for item in batch["results"]))

    def test_batch_manifest_accumulates_completed_separate_invocations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            cfg = replace(
                cfg,
                filter_type="smooth_sharp",
                sharp_edge_width_fraction=0.125,
                sigma_grid=2.0,
                sigma_grids=(2.0,),
            )
            process_batch(cfg, 1, (2.0,))
            process_batch(cfg, 1, (3.0,))
            batch = json.loads(
                cfg.batch_manifest_path(1).read_text(encoding="utf-8")
            )
            self.assertEqual(batch["sigma_grids"], [2.0, 3.0])
            self.assertTrue(all(item["complete"] for item in batch["results"]))

    def test_smooth_sharp_result_is_full_domain_and_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            cfg = replace(
                cfg,
                filter_type="smooth_sharp",
                sharp_edge_width_fraction=0.125,
                sigma_grid=2.0,
                sigma_grids=(2.0,),
            )
            process_full(cfg, 1, 2.0)
            final = finalize_result(cfg, 1, 2.0)
            self.assertEqual(
                final.name, "t000001_filter_smooth_sharp_a0p125kc_sigma_2"
            )
            result = open_complete_result(final)
            self.assertEqual(result.attrs["filter_type"], "smooth_sharp")
            self.assertEqual(tuple(result["pi"].shape), cfg.full_shape_zyx)
            manifest = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["filter_type"], "smooth_sharp")
            self.assertEqual(manifest["sharp_edge_width_fraction"], 0.125)

    def test_relative_smooth_sharp_width_is_scale_invariant_and_namespaced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            cfg = replace(
                cfg,
                filter_type="smooth_sharp",
                sharp_edge_width_fraction=0.125,
                sigma_grid=2.0,
                sigma_grids=(2.0, 4.0),
            )
            self.assertIn("a0p125kc", cfg.result_id(1, 2.0))

            process_full(cfg, 1, 2.0)
            final = finalize_result(cfg, 1, 2.0)
            result = open_complete_result(final)
            self.assertEqual(result.attrs["sharp_edge_width_fraction"], 0.125)

    def test_multi_sigma_batch_reuses_raw_gradients_and_first_axis_fft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            batch_cfg, _ = fixture(root / "batch")
            sigmas = (1.0, 2.0)
            with patch(
                "jhtdb_pipeline.processing.axis2_spectrum",
                wraps=physics_axis2_spectrum,
            ) as cached_fft:
                paths = process_batch(batch_cfg, 1, sigmas)
            self.assertEqual(cached_fft.call_count, 12)
            self.assertTrue(all((path / "COMPLETE").is_file() for path in paths))
            for sigma, path in zip(sigmas, paths):
                qa = json.loads((path / "qa.json").read_text(encoding="utf-8"))
                self.assertTrue(qa["reuse"]["raw_gradients"])
                self.assertTrue(qa["reuse"]["first_axis_fft_spectra"])
                self.assertEqual(open_complete_result(path)["regime"].dtype, np.dtype("u1"))

            normal_cfg, _ = fixture(root / "normal")
            process_full(normal_cfg, 1, 1.0)
            normal_path = finalize_result(normal_cfg, 1, 1.0)
            batch_result = open_complete_result(paths[0])
            normal_result = open_complete_result(normal_path)
            for name in (
                "velocity_bar", "gradient_bar", "work_full", "work_resolved",
                "pi", "s_bar", "regime",
            ):
                np.testing.assert_array_equal(batch_result[name][:], normal_result[name][:])


    def test_full_pipeline_and_persistent_finalization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, velocity = fixture(Path(temporary))
            batch_cfg = replace(
                cfg,
                sigma_grid=1.0,
                sigma_grids=(1.0, 2.0, 3.0),
            )
            plan = resource_plan(batch_cfg)
            expected_result_bytes = 16**3 * 65
            self.assertEqual(
                plan["result_GiB"], expected_result_bytes / 1024**3
            )
            self.assertEqual(plan["configured_sigma_count"], 3)
            self.assertEqual(
                plan["batch_result_GiB"],
                3 * expected_result_bytes / 1024**3,
            )
            staging = process_full(cfg, 1)
            self.assertTrue((staging / result_zarr_name(cfg.sigma_grid)).is_dir())
            divergence = json.loads(
                (staging / "divergence.json").read_text(encoding="utf-8")
            )
            self.assertTrue(divergence["passed"])
            self.assertTrue(divergence["unfiltered"]["passed"])
            self.assertTrue(divergence["filtered"]["passed"])
            final = finalize_result(cfg, 1)
            self.assertTrue((final / "COMPLETE").is_file())
            self.assertTrue((final / "manifest.json").is_file())
            self.assertTrue((final / "s_bar_qa.json").is_file())
            self.assertTrue((final / "s_bar_global_totals.html").is_file())
            self.assertTrue((final / "cq.json").is_file())
            self.assertTrue((final / "cq.html").is_file())
            self.assertTrue((final / "weak_asymmetry.json").is_file())
            self.assertTrue((final / "weak_asymmetry.html").is_file())
            self.assertEqual(run_sbar_qa(cfg, 1)["scope"], "full_domain")
            result = open_complete_result(final)
            self.assertEqual(result["velocity"].shape, (3, 16, 16, 16))
            self.assertEqual(result["gradient"].shape, (3, 3, 16, 16, 16))
            self.assertEqual(result["work_full"].shape, (16, 16, 16))
            self.assertEqual(result["regime"].shape, (16, 16, 16))
            np.testing.assert_allclose(result["velocity"][0], velocity[0])
            expected_filtered = spectral_gaussian(velocity[0], cfg.sigma_grid)
            np.testing.assert_allclose(
                result["velocity_bar"][0], expected_filtered, rtol=2e-5, atol=2e-6
            )
            expected_gradient = spectral_derivative(
                velocity[0], 2, cfg.domain_length
            )
            np.testing.assert_allclose(
                result["gradient"][0, 0], expected_gradient, rtol=2e-5, atol=2e-6
            )
            self.assertTrue(np.all(np.isfinite(result["work_full"][:])))
            self.assertTrue(np.all(np.isfinite(result["work_resolved"][:])))
            filtered = np.stack(
                [spectral_gaussian(velocity[i], cfg.sigma_grid) for i in range(3)]
            )
            gradient_bar = np.empty((3, 3, 16, 16, 16), dtype=np.float32)
            tau = np.empty((3, 3, 16, 16, 16), dtype=np.float32)
            for i in range(3):
                for j in range(3):
                    gradient_bar[i, j] = spectral_derivative(
                        filtered[i], 2 - j, cfg.domain_length
                    )
                    tau[i, j] = (
                        spectral_gaussian(velocity[i] * velocity[j], cfg.sigma_grid)
                        - filtered[i] * filtered[j]
                    )
            filtered_divergence = sum(gradient_bar[i, i] for i in range(3))
            self.assertEqual(
                divergence["filtered"]["point_count"], int(np.prod(cfg.grid_shape))
            )
            self.assertAlmostEqual(
                divergence["filtered"]["maximum_abs_divergence"],
                float(np.max(np.abs(filtered_divergence))),
                delta=2.0e-6,
            )
            expected_pi = np.einsum("ijzyx,ijzyx->zyx", tau, gradient_bar)
            transport = np.einsum("izyx,ijzyx->jzyx", filtered, tau)
            expected_s_bar = sum(
                spectral_derivative(transport[j], 2 - j, cfg.domain_length)
                for j in range(3)
            )
            np.testing.assert_allclose(
                result["pi"][:], expected_pi, rtol=3e-5, atol=3e-6
            )
            np.testing.assert_allclose(
                result["s_bar"][:], expected_s_bar, rtol=3e-5, atol=3e-6
            )
            np.testing.assert_allclose(
                result["work_full"][:],
                result["work_resolved"][:] - result["pi"][:] + result["s_bar"][:],
                rtol=5e-5,
                atol=5e-6,
            )
            self.assertFalse(cfg.workspace_path(1).exists())
            self.assertFalse(any(final.rglob("*.part-*")))
            manifest = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 7)
            self.assertEqual(manifest["field_scopes"]["regime"], "full_domain")
            self.assertEqual(manifest["s_bar_qa_report_version"], 3)
            self.assertIn("s_bar_qa_report_hash", manifest)
            self.assertTrue(manifest["cq_passed"])
            self.assertIn("cq_report_hash", manifest)
            self.assertTrue(manifest["weak_asymmetry_passed"])
            self.assertIn("weak_asymmetry_report_hash", manifest)
            self.assertEqual(
                json.loads((final / "COMPLETE").read_text(encoding="utf-8"))[
                    "manifest_hash"
                ],
                result.attrs["manifest_hash"],
            )
            self.assertEqual(set(manifest["fields"]), {
                "velocity_bar", "gradient_bar",
                "work_full", "work_resolved", "pi", "s_bar", "regime",
            })
            relaxed_cfg = replace(
                cfg, energy_identity_relative_rms_max=5.0e-4
            )
            with patch(
                "jhtdb_pipeline.sbar_qa.compute_sbar_qa",
                side_effect=AssertionError("full-field scan was not expected"),
            ):
                self.assertEqual(ensure_sbar_result(relaxed_cfg, 1), final)
            threshold_only_report = json.loads(
                (final / "s_bar_qa.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                threshold_only_report["metrics"]
                ["identity_relative_residual_rms"]["threshold"],
                5.0e-4,
            )
            for name in (
                "s_bar_qa.json",
                "s_bar_global_totals.html",
                "cq.json",
                "cq.html",
                "weak_asymmetry.json",
                "weak_asymmetry.html",
            ):
                (final / name).unlink()
            self.assertEqual(process_full(cfg, 1), final)
            refreshed_s_bar = json.loads(
                (final / "s_bar_qa.json").read_text(encoding="utf-8")
            )
            self.assertEqual(refreshed_s_bar["report_version"], 3)
            self.assertNotIn("s_bar_rel_self", refreshed_s_bar["metrics"])
            self.assertTrue((final / "s_bar_global_totals.html").is_file())
            self.assertTrue((final / "cq.json").is_file())
            self.assertTrue((final / "cq.html").is_file())
            self.assertTrue((final / "weak_asymmetry.json").is_file())
            self.assertTrue((final / "weak_asymmetry.html").is_file())

    def test_legacy_complete_result_is_replaced_only_after_new_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            final = cfg.result_path(1)
            legacy = zarr.open_group(str(final / "obsolete_result.zarr"), mode="w")
            legacy.attrs["status"] = "complete"
            (final / "COMPLETE").write_text("{}\n", encoding="utf-8")

            staging = process_full(cfg, 1)
            self.assertTrue((final / "COMPLETE").is_file())
            self.assertTrue((final / "obsolete_result.zarr").is_dir())
            self.assertTrue((staging / result_zarr_name(cfg.sigma_grid)).is_dir())

            replaced = finalize_result(cfg, 1)
            self.assertEqual(replaced, final)
            self.assertFalse((final / "obsolete_result.zarr").exists())
            self.assertTrue((final / result_zarr_name(cfg.sigma_grid)).is_dir())
            self.assertIn("pi", open_complete_result(final))

    def test_restart_reuses_validated_filtered_velocity_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary))
            cfg = replace(cfg, cleanup_scratch_on_success=False)
            process_full(cfg, 1)
            final = finalize_result(cfg, 1)
            root = zarr.open_group(
                str(final / result_zarr_name(cfg.sigma_grid)), mode="a"
            )
            (final / "COMPLETE").unlink()
            shutil.rmtree(final)

            with patch(
                "jhtdb_pipeline.processing.filter_field",
                wraps=processing_filter_field,
            ) as filtered:
                staging = process_full(cfg, 1)

            qa = json.loads((staging / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(qa["reuse"]["filtered_velocity"])
            self.assertEqual(filtered.call_count, 9)


    def test_divergence_failure_never_creates_complete_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cfg, _ = fixture(Path(temporary), compressible=True)
            with self.assertRaisesRegex(RuntimeError, "divergence"):
                process_full(cfg, 1)
            self.assertFalse((cfg.result_path(1) / "COMPLETE").exists())
            report = json.loads(
                (cfg.staging_result_path(1) / "divergence.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(report["passed"])
            self.assertFalse(report["unfiltered"]["passed"])
            self.assertFalse(report["filtered"]["passed"])


if __name__ == "__main__":
    unittest.main()
