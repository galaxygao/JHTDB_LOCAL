"""Independent brute-force checks for the full-grid distance-connectivity engine."""
import csv
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest
from scipy.sparse.csgraph import connected_components

from qpower_analysis.strong_event_h0 import build_engine


@pytest.fixture(scope='module')
def engine():
    return build_engine()


def check_graph(engine, tmp_path, mask):
    points = np.argwhere(mask)
    shape = np.array(mask.shape)
    delta = np.abs(points[:, None, :] - points[None, :, :])
    delta = np.minimum(delta, shape-delta)
    squared_distance = np.sum(delta**2, axis=2)
    packed = tmp_path/'mask.bits'
    np.packbits(mask.ravel(), bitorder='little').tofile(packed)
    subprocess.run([str(engine), str(packed), *map(str, mask.shape), str(tmp_path), '1'],
                   check=True, capture_output=True, text=True)
    with (tmp_path/'connectivity_grid.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        r2 = int(row['r_squared_grid'])
        count, labels = connected_components(squared_distance <= r2, directed=False)
        sizes = np.bincount(labels)
        assert int(row['structure_count']) == count
        assert int(row['largest_size']) == sizes.max()
        for k in (10, 100, 1000):
            assert int(row[f'count_ge{k}']) == int(np.count_nonzero(sizes >= k))
        np.testing.assert_allclose(float(row['effective_structure_count']),
                                   len(points)**2 / np.sum(sizes.astype(float)**2))
    # Verify every actual pair-distance, including distances absent from the output
    # after the graph becomes connected or in intervals with no lattice shell.
    for r2 in np.unique(squared_distance):
        expected, _ = connected_components(squared_distance <= r2, directed=False)
        last = [r for r in rows if int(r['r_squared_grid']) <= r2][-1]
        assert int(last['structure_count']) == expected
    assert sum(int(r['merges_at_r']) for r in rows) == len(points)-1
    for path in tmp_path.glob('sample_r2_*.csv'):
        r2 = int(path.stem.rsplit('_', 1)[1])
        _, expected = connected_components(squared_distance <= r2, directed=False)
        with path.open() as handle:
            sample = list(csv.DictReader(handle))
        actual = np.array([int(r['component_id']) for r in sample])
        np.testing.assert_array_equal(actual[:, None] == actual[None, :],
                                      expected[:, None] == expected[None, :])
    return json.loads((tmp_path/'engine_summary.json').read_text())


@pytest.mark.parametrize('points,death2', [
    ([(0, 0, 0)], 0),
    ([(0, 0, 0), (0, 0, 7)], 1),  # periodic boundary
    ([(0, 0, 0), (0, 1, 1)], 2),  # diagonal Euclidean distance
    ([(0, 0, 0), (1, 1, 1)], 3),
    ([(0, 0, 0), (0, 0, 3)], 9),  # background must not bridge the gap
    ([(0, 0, 0), (0, 0, 2), (0, 0, 4)], 4),  # transitive chain
    ([(0, 0, 0), (4, 4, 4)], 48),  # even-size periodic antipode
])
def test_known_merge_distances(engine, tmp_path, points, death2):
    mask = np.zeros((8, 8, 8), dtype=bool)
    mask[tuple(np.array(points).T)] = True
    result = check_graph(engine, tmp_path, mask)
    assert result['connectivity_r_squared_grid'] == death2


@pytest.mark.parametrize('seed,density', [(1, .02), (2, .05), (3, .15), (4, .5)])
def test_all_shell_counts_and_partitions_against_brute_force(engine, tmp_path, seed, density):
    mask = np.random.default_rng(seed).random((8, 10, 8)) < density
    check_graph(engine, tmp_path, mask)
