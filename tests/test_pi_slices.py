from __future__ import annotations

import numpy as np
import pytest

from pi_slices.plot_orthogonal_slices import (
    _replace_or_number,
    build_figure,
    build_static_figure,
    extract_orthogonal_planes,
    extract_plane,
    parse_planes,
    symmetric_color_limit,
)


def test_atomic_replace_uses_numbered_name_when_target_is_busy(tmp_path, monkeypatch) -> None:
    target = tmp_path / "slice.png"
    target.write_bytes(b"old")
    temporary = tmp_path / ".slice.tmp.png"
    temporary.write_bytes(b"new")
    original_replace = type(temporary).replace

    def busy_once(path, destination):
        if destination == target:
            raise OSError(22, "busy")
        return original_replace(path, destination)

    monkeypatch.setattr(type(temporary), "replace", busy_once)
    actual = _replace_or_number(temporary, target)
    assert actual.name == "slice_1.png"
    assert actual.read_bytes() == b"new"
    assert target.read_bytes() == b"old"


def test_extract_two_planes_preserves_zyx_orientation() -> None:
    field = np.arange(4 * 6 * 8, dtype=np.float32).reshape(4, 6, 8)
    xy = extract_plane(field, "xy", 2, sample_step=2, domain_length=2.0)
    yz = extract_plane(field, "yz", 3, sample_step=2, domain_length=2.0)

    np.testing.assert_array_equal(
        xy.values, field[2][np.ix_([0, 2, 4, 5], [0, 2, 4, 6, 7])]
    )
    np.testing.assert_array_equal(
        yz.values, field[:, :, 3][np.ix_([0, 2, 3], [0, 2, 4, 5])]
    )
    assert xy.values.shape == xy.x.shape == xy.y.shape == xy.z.shape
    assert yz.values.shape == yz.x.shape == yz.y.shape == yz.z.shape
    assert np.all(xy.z == 1.0)
    assert np.all(yz.x == 0.75)


def test_orthogonal_planes_share_exact_full_length_intersection() -> None:
    field = np.arange(7 * 8 * 9, dtype=np.float32).reshape(7, 8, 9)
    yz, xy, xz = extract_orthogonal_planes(
        field,
        ("yz", "xy", "xz"),
        {"x": 2, "y": 5, "z": 4},
        sample_step=3,
        domain_length=9.0,
    )

    yz_z = np.flatnonzero(np.isclose(yz.z[:, 0], 4.0 * 9.0 / 7.0))
    xy_x = np.flatnonzero(np.isclose(xy.x[0, :], 2.0))
    yz_y = np.flatnonzero(np.isclose(yz.y[0, :], 5.0 * 9.0 / 8.0))
    xz_x = np.flatnonzero(np.isclose(xz.x[0, :], 2.0))
    xy_y = np.flatnonzero(np.isclose(xy.y[:, 0], 5.0 * 9.0 / 8.0))
    xz_z = np.flatnonzero(np.isclose(xz.z[:, 0], 4.0 * 9.0 / 7.0))
    assert yz_z.tolist() == [2]
    assert xy_x.tolist() == [1]
    assert yz_y.size == xz_x.size == xy_y.size == xz_z.size == 1
    np.testing.assert_array_equal(yz.values[yz_z[0], :], xy.values[:, xy_x[0]])
    np.testing.assert_array_equal(yz.values[:, yz_y[0]], xz.values[:, xz_x[0]])
    np.testing.assert_array_equal(xy.values[xy_y[0], :], xz.values[xz_z[0], :])
    assert yz.y.min() == xy.y.min() == 0.0
    assert yz.y.max() == xy.y.max() == 7.0 * 9.0 / 8.0


def test_plane_parser_requires_two_different_coordinate_planes() -> None:
    assert parse_planes("yz,xz") == ("yz", "xz")
    assert parse_planes("yz,xy,xz") == ("yz", "xy", "xz")
    with pytest.raises(Exception):
        parse_planes("xy,xy")
    with pytest.raises(Exception):
        parse_planes("xy,ab")


def test_symmetric_limit_and_figure_share_one_color_axis() -> None:
    field = np.arange(4 * 6 * 8, dtype=np.float32).reshape(4, 6, 8) - 96.0
    planes = [
        extract_plane(field, "yz", 3, sample_step=2, domain_length=2.0),
        extract_plane(field, "xz", 2, sample_step=2, domain_length=2.0),
    ]
    limit = symmetric_color_limit(planes, 100.0, None)
    figure = build_figure(
        planes,
        shape_zyx=field.shape,
        domain_length=2.0,
        color_limit=limit,
        title="test",
        quantity_label="Pi",
    )

    assert limit == max(float(np.max(np.abs(item.values))) for item in planes)
    assert [trace.type for trace in figure.data] == ["surface", "surface", "scatter3d"]
    assert figure.layout.coloraxis.cmin == -limit
    assert figure.layout.coloraxis.cmax == limit

    static_figure = build_static_figure(
        planes,
        shape_zyx=field.shape,
        domain_length=2.0,
        color_limit=limit,
        panel_label="(d)",
    )
    try:
        assert len(static_figure.axes) == 2
        assert len(static_figure.axes[0].collections) == 1
        assert static_figure.axes[0].collections[0].__class__.__name__ == "Poly3DCollection"
    finally:
        static_figure.clear()


def test_three_plane_figures_have_three_surfaces_and_intersections() -> None:
    field = np.arange(7 * 8 * 9, dtype=np.float32).reshape(7, 8, 9) - 252.0
    planes = extract_orthogonal_planes(
        field,
        ("yz", "xy", "xz"),
        {"x": 2, "y": 5, "z": 4},
        sample_step=3,
        domain_length=9.0,
    )
    limit = symmetric_color_limit(planes, 100.0, None)
    interactive = build_figure(
        planes,
        shape_zyx=field.shape,
        domain_length=9.0,
        color_limit=limit,
        title="three planes",
        quantity_label="Pi",
    )
    assert [trace.type for trace in interactive.data] == [
        "surface", "surface", "surface", "scatter3d", "scatter3d", "scatter3d"
    ]

    static = build_static_figure(
        planes,
        shape_zyx=field.shape,
        domain_length=9.0,
        color_limit=limit,
        panel_label="(d)",
    )
    try:
        assert len(static.axes[0].collections) == 1
    finally:
        static.clear()
