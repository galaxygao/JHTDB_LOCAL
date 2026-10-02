import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


MODULE_PATH = Path(__file__).parents[1] / "qpower_analysis.py"
SPEC = importlib.util.spec_from_file_location("qpower_analysis_standalone", MODULE_PATH)
qpa = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = qpa
SPEC.loader.exec_module(qpa)


def test_q_algebra():
    velocity = np.array([1.0, 2.0, 3.0])[:, None, None, None]
    gradient = np.array([4.0, 5.0, 6.0])[:, None, None, None]
    q, u2, q_rms, u2_mean = qpa.core_fields(velocity, gradient)
    assert q.item() == -32.0
    assert u2.item() == 14.0
    assert q_rms == 32.0
    assert u2_mean == 14.0


def test_spectral_gradient_periodic_field():
    n = 16
    x = np.arange(n) * 2 * np.pi / n
    z, y, x3 = np.meshgrid(x, x, x, indexing="ij")
    pressure = np.sin(x3) + 2 * np.cos(y) + 3 * np.sin(2 * z)
    gradient = qpa.pressure_gradient(pressure, [2*np.pi] * 3, "spectral")
    assert np.allclose(gradient[0], np.cos(x3), atol=1e-11)
    assert np.allclose(gradient[1], -2*np.sin(y), atol=1e-11)
    assert np.allclose(gradient[2], 6*np.cos(2*z), atol=1e-11)


def test_masks_are_strict():
    q = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    assert qpa.event_mask(q, 1.0, 1.0, "positive").tolist() == [False, False, False, False, True]
    assert qpa.event_mask(q, 1.0, 1.0, "negative").tolist() == [True, False, False, False, False]
    assert qpa.event_mask(q, 1.0, 1.0, "absolute").tolist() == [True, False, False, False, True]


def test_voxel_surface_removes_shared_faces_and_clips_edge():
    points, faces = qpa.voxel_surface(np.ones((1, 1, 2), dtype=bool), 2, (1, 2, 3))
    assert len(faces) == 20  # Two cubes, ten exposed quads, no shared interior face.
    np.testing.assert_allclose(points.min(axis=0), [-.5, -.5, -.5])
    np.testing.assert_allclose(points.max(axis=0), [2.5, 1.5, .5])


def test_overlay_has_separate_intersection_points(tmp_path, monkeypatch):
    captured = []
    monkeypatch.setattr(qpa.go.Figure, 'write_html', lambda self, *a, **k: captured.append(self))
    a = np.array([[[True, True, False]]])
    b = np.array([[[False, True, True]]])
    qpa.region_html(a, b, tmp_path / 'overlay.html')
    traces = captured[0].data
    assert len(traces) == 3
    for index, trace in enumerate(traces):
        assert trace.type == 'scatter3d'
        assert len(trace.x) == 1
        assert 0 < trace.marker.opacity < 1
    assert len({trace.marker.color for trace in traces}) == 3
    assert set(traces[0].x) == {0}
    assert set(traces[1].x) == {2}
    assert set(traces[2].x) == {1}


def test_preflight_rejects_missing_pressure(tmp_path):
    velocity = np.zeros((3, 2, 2, 2), dtype=np.float32)
    path = tmp_path / "velocity.npy"
    np.save(path, velocity)
    config = {"frames": [{"frame": 1, "velocity_path": str(path)}]}
    with pytest.raises(qpa.PreflightError, match="pressure data is required"):
        qpa.preflight(config)


def test_random_overlap_baseline():
    result = qpa.random_overlap_baseline(20, 40, 100, 16)
    assert result['random_p_a_given_b'] == .2
    assert result['random_p_b_given_a'] == .4
    assert result['p_a_given_b_over_random'] == 2
    assert result['p_b_given_a_over_random'] == 2
    assert qpa.random_overlap_baseline(20, 40, 100, 8)['p_a_given_b_over_random'] == 1
    assert qpa.random_overlap_baseline(20, 40, 100, 0)['p_a_given_b_over_random'] == 0
    empty = qpa.random_overlap_baseline(0, 40, 100, 0)
    assert empty['random_p_a_given_b'] == 0
    assert np.isnan(empty['random_p_b_given_a'])
    assert np.isnan(empty['p_a_given_b_over_random'])
