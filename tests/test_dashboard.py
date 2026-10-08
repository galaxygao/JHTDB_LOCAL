from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml
from streamlit.testing.v1 import AppTest

from jhtdb_pipeline.dashboard import (
    _continuous_figure,
    _symmetric_color_limit,
    _symlog_transform,
    _weak_asymmetry_figure,
    _global_totals_figure,
    complete_result_paths,
    result_selection_catalog,
    energy_identity_residual,
    extract_gradient_slice,
    extract_scalar_slice,
    extract_slice,
    sbar_metric_rows,
    weak_asymmetry_rows,
    spatial_axis_length,
    comparison_slices,
)
from jhtdb_pipeline.processing import process_batch
from test_processing import fixture


class DashboardTests(unittest.TestCase):
    def test_comparisons_align_raw_and_sampled_fields_in_all_three_planes(self):
        vector = np.arange(3 * 16**3).reshape(3, 16, 16, 16)
        fields = {"velocity": vector, "velocity_bar": vector[:, ::2, ::2, ::2]}

        class Result(dict):
            attrs = {"field_sampling": {"velocity_bar": {"stride_xyz": [2, 2, 2]}}}

        result = Result(fields)
        for axis in ("z", "y", "x"):
            raw, filtered = comparison_slices(result, "velocity_bar", axis, 14, 1)
            np.testing.assert_array_equal(raw, filtered)
            self.assertEqual(raw.shape, (8, 8))
        with self.assertRaisesRegex(ValueError, "sampling lattice"):
            comparison_slices(result, "velocity_bar", "z", 15, 1)

    def test_sampled_figures_use_original_grid_coordinates(self):
        figure = _continuous_figure(np.zeros((512, 512)), "sampled velocity", storage_stride=2)
        np.testing.assert_array_equal(figure.data[0].x, np.arange(0, 1024, 2))
        np.testing.assert_array_equal(figure.data[0].y, np.arange(0, 1024, 2))
        self.assertEqual(list(figure.layout.xaxis.range), [0, 1023])

    def test_robust_symmetric_color_limit_ignores_sparse_extreme(self) -> None:
        values = np.concatenate((np.linspace(-2.0, 2.0, 10_000), [1_000.0]))
        robust_limit = _symmetric_color_limit(values, 99.0)
        self.assertLess(robust_limit, 2.0)
        self.assertGreater(robust_limit, 1.9)
        self.assertEqual(_symmetric_color_limit(values), 1_000.0)

    def test_symmetric_color_limit_handles_empty_and_constant_fields(self) -> None:
        self.assertEqual(_symmetric_color_limit(np.array([np.nan, np.inf])), 1.0)
        self.assertEqual(_symmetric_color_limit(np.zeros((2, 2)), 99.0), 1.0)
        with self.assertRaisesRegex(ValueError, "percentile"):
            _symmetric_color_limit(np.ones((2, 2)), 0.0)

    def test_symlog_transform_is_symmetric_and_preserves_zero(self) -> None:
        values = np.array([-100.0, -1.0, 0.0, 1.0, 100.0])
        transformed = _symlog_transform(values, 1.0)
        self.assertEqual(transformed[2], 0.0)
        np.testing.assert_allclose(transformed[:2], -transformed[:2:-1])
        with self.assertRaisesRegex(ValueError, "linear_threshold"):
            _symlog_transform(values, 0.0)

    def test_continuous_figure_keeps_full_domain_coordinates_when_downsampled(self) -> None:
        values = np.zeros((1024, 1024), dtype=np.float32)
        figure = _continuous_figure(values, "full-domain work")
        trace = figure.data[0]
        self.assertEqual(trace.z.shape, (512, 512))
        np.testing.assert_array_equal(trace.x, np.arange(0, 1024, 2))
        np.testing.assert_array_equal(trace.y, np.arange(0, 1024, 2))
        self.assertEqual(list(figure.layout.xaxis.range), [0, 1023])
        self.assertEqual(list(figure.layout.yaxis.range), [0, 1023])
        self.assertIn("stride=2", figure.layout.xaxis.title.text)

    def test_slice_axis_mapping(self) -> None:
        vector = np.arange(3 * 4 * 5 * 6).reshape(3, 4, 5, 6)
        scalar = np.arange(4 * 5 * 6).reshape(4, 5, 6)
        gradient = np.arange(3 * 3 * 4 * 5 * 6).reshape(3, 3, 4, 5, 6)
        np.testing.assert_array_equal(extract_slice(vector, 1, "x", 2), vector[1, :, :, 2])
        np.testing.assert_array_equal(extract_scalar_slice(scalar, "y", 3), scalar[:, 3, :])
        np.testing.assert_array_equal(
            extract_gradient_slice(gradient, 1, 2, "z", 3), gradient[1, 2, 3, :, :]
        )
        self.assertEqual(spatial_axis_length(vector, "x"), 6)
        self.assertEqual(spatial_axis_length(vector, "y"), 5)
        self.assertEqual(spatial_axis_length(vector, "z"), 4)

    def test_global_totals_bar_order(self) -> None:
        report = {
            "scope": "full_domain",
            "global_totals": {
                "s_bar": 1.0,
                "pi": 2.0,
                "work_resolved": 3.0,
                "work_full": 4.0,
            },
        }
        figure = _global_totals_figure(report)
        self.assertEqual(list(figure.data[0].y), [1.0, 2.0, 3.0, 4.0])


    def test_weak_asymmetry_figure_and_rows_keep_sign_convention(self) -> None:
        report = {
            "global": {"pi_sum": -1.0},
            "positive_backscatter": {"sum": 9.0, "volume_fraction": 0.4},
            "negative_forward": {"sum": -10.0, "volume_fraction": 0.6},
            "zero": {"volume_fraction": 0.0},
        }
        figure = _weak_asymmetry_figure(report)
        self.assertEqual(list(figure.data[0].y), [9.0, -10.0, -1.0])
        rows = weak_asymmetry_rows(report)
        self.assertEqual(rows[0]["sign"], "positive/backscatter")
        self.assertEqual(rows[1]["sign"], "negative/forward")


    def test_sbar_metric_rows_expose_thresholds_and_status(self) -> None:
        report = {
            "metrics": {
                "identity_relative_residual_rms": {
                    "value": 2.0e-5,
                    "residual_rms": 8.0e-5,
                    "joint_energy_rms": 4.0,
                    "maximum_abs": 3.0e-3,
                    "threshold": 1.0e-4,
                    "passed": True,
                },
                "s_bar_vs_pi_net": {
                    "value": None,
                    "threshold": 1.0e-2,
                    "passed": False,
                    "error": "denominator is zero",
                },
            }
        }
        rows = sbar_metric_rows(report)
        self.assertEqual([row["状态"] for row in rows], ["通过", "失败"])
        self.assertEqual(rows[1]["值"], "不可定义")
        self.assertEqual(rows[1]["说明"], "denominator is zero")
        self.assertIn("residual_rms=", rows[0]["说明"])
        self.assertIn("joint_energy_rms=", rows[0]["说明"])

    def test_energy_identity_residual_uses_documented_signs(self) -> None:
        full = np.array([[7.0, 8.0]])
        resolved = np.array([[10.0, 10.0]])
        pi = np.array([[2.0, 3.0]])
        s_bar = np.array([[-1.0, 1.0]])
        np.testing.assert_array_equal(
            energy_identity_residual(full, resolved, pi, s_bar),
            np.array([[0.0, 0.0]]),
        )

    def test_only_complete_persistent_results_are_listed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            complete = root / "t000001_sigma_1"
            incomplete = root / "t000002_sigma_1"
            hidden = root / ".staging"
            for path in (complete, incomplete, hidden):
                path.mkdir()
            (complete / "COMPLETE").write_text("{}\n", encoding="utf-8")
            self.assertEqual(complete_result_paths(root), [complete])

    def test_result_selectors_use_manifest_without_opening_zarr(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            specifications = (
                ("gaussian", {"filter_type": "gaussian"}),
                (
                    "relative",
                    {
                        "filter_type": "smooth_sharp",
                        "sharp_edge_width_fraction": 0.1171875,
                    },
                ),
            )
            paths = []
            for index, (name, filter_metadata) in enumerate(specifications, start=1):
                path = root / name
                path.mkdir()
                manifest = {
                    "schema_version": 7,
                    "time_index": 1,
                    "physical_time": 0.0,
                    "sigma_grid": float(index * 10),
                    **filter_metadata,
                }
                (path / "manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
                paths.append(path)

            catalog = result_selection_catalog(paths)
            self.assertEqual(len(catalog), 2)
            self.assertEqual(catalog[0]["smoothing_label"], "不适用")
            self.assertEqual(
                catalog[1]["smoothing_key"],
                ("fraction_of_cutoff", 0.1171875),
            )


@pytest.mark.parametrize("entry", ["dashboard.py", "src/jhtdb_pipeline/dashboard.py"])
def test_dashboard_import_with_streamlit_script_directory_first(entry):
    project = Path(__file__).resolve().parents[1]
    script = project / entry
    probe = (
        "import runpy, sys; from pathlib import Path; "
        "sys.path.insert(0, str(Path(sys.argv[1]).parent)); "
        "runpy.run_path(sys.argv[1], run_name='_dashboard_import_probe'); "
        "from jhtdb_pipeline.store import open_complete_result; "
        "assert callable(open_complete_result)"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe, str(script)],
        cwd=project, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_full_field_gui_all_pages_and_boundary_slices(tmp_path, monkeypatch):
    cfg, _ = fixture(tmp_path)
    cfg = replace(cfg, fft_cache_mode='memmap', sigma_grids=(1.0, 2.0))
    paths = process_batch(cfg, 1)
    sbar_passed = json.loads((paths[0] / "s_bar_qa.json").read_text())["passed"]
    config = yaml.safe_load(Path('configs/pipeline.macos.yaml').read_text())
    config['platform'] = {key: str(getattr(cfg, key)) for key in ('state_root', 'run_root', 'result_root')}
    # GUI metadata discovery must read full test arrays, without allocating a production field.
    config_path = tmp_path / 'gui.yaml'
    config_path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv('JHTDB_PIPELINE_CONFIG', str(config_path))
    app = AppTest.from_file(str(Path('src/jhtdb_pipeline/dashboard.py').resolve()), default_timeout=20)
    app.run()
    assert not app.exception
    app.sidebar.button[0].click().run()
    assert not app.exception
    for page in app.sidebar.radio[0].options:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, str(app.exception)
        if page == "全域 S̄ QA" and not sbar_passed:
            assert [item.value for item in app.error] == ["全域 S̄ QA：失败；正式数据仍保留用于诊断"]
        else:
            assert not app.error, (page, [item.value for item in app.error])
        if app.sidebar.slider:
            boundary = 14 if page in ("速度对比", "梯度对比") else 15
            assert app.sidebar.slider[0].max == boundary
            app.sidebar.slider[0].set_value(0).run()
            assert not app.exception, str(app.exception)
            app.sidebar.slider[0].set_value(boundary).run()
            assert not app.exception, str(app.exception)

if __name__ == "__main__":
    unittest.main()


def test_result_catalog_prefers_current_schema_when_old_results_coexist(tmp_path):
    paths = []
    for name, version, sigma in [('old', 8, 10), ('current', 9, 10), ('other', 8, 15)]:
        path = tmp_path / name
        path.mkdir()
        (path / 'manifest.json').write_text(json.dumps({
            'schema_version': version, 'time_index': 1,
            'sigma_grid': sigma, 'filter_type': 'gaussian',
        }))
        paths.append(path)
    catalog = result_selection_catalog(paths)
    assert [item['path'].name for item in catalog] == ['current', 'other']
