"""Safety and routing contracts for schema rebuilds; no production computation."""
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('rebuild_v7', Path(__file__).resolve().parents[1] / 'scripts/rebuild_v7.py')
rebuild = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rebuild)


def source_result(tmp_path, version=6):
    source = tmp_path / 'old' / 'result'
    source.mkdir(parents=True)
    payload = dict(schema_version=version, dataset='isotropic1024coarse', time_index=7,
                   sigma_grid=15, filter_type='smooth_sharp', sharp_edge_width_fraction=.1)
    (source / 'manifest.json').write_text(json.dumps(payload))
    (source / 'COMPLETE').write_text('complete')
    return source


def arguments(source, destination):
    return ['--config', 'configs/pipeline.macos.yaml', '--source-result', str(source), '--result-root', str(destination)]


def test_plan_is_read_only_and_preserves_source_parameters(tmp_path, monkeypatch, capsys):
    source = source_result(tmp_path)
    before = (source / 'manifest.json').read_bytes()
    destination = tmp_path / 'new'
    monkeypatch.setattr(rebuild, 'validate_snapshot', lambda *a: pytest.fail('dry run validated data'))
    monkeypatch.setattr(rebuild, 'process_batch', lambda *a: pytest.fail('dry run computed data'))
    assert rebuild.main(arguments(source, destination)) == 0
    plan = json.loads(capsys.readouterr().out)
    assert (plan['time_index'], plan['sigma_grid'], plan['target_schema']) == (7, 15, 7)
    assert 'a0p1kc' in plan['destination']
    assert not destination.exists()
    assert (source / 'manifest.json').read_bytes() == before


@pytest.mark.parametrize('relative', ['', 'old', 'old/result', 'old/result/nested'])
def test_reject_overlapping_roots(tmp_path, relative):
    source = source_result(tmp_path)
    with pytest.raises(SystemExit):
        rebuild.main(arguments(source, tmp_path / relative))


def test_failed_validation_prevents_computation(tmp_path, monkeypatch):
    source = source_result(tmp_path, 7)
    def fail(*args):
        raise RuntimeError('checksum mismatch')
    monkeypatch.setattr(rebuild, 'validate_snapshot', fail)
    monkeypatch.setattr(rebuild, 'process_batch', lambda *a: pytest.fail('computed invalid input'))
    with pytest.raises(RuntimeError, match='checksum'):
        rebuild.main(arguments(source, tmp_path / 'new') + ['--execute'])


def test_rebuild_routes_to_separate_destination(tmp_path, monkeypatch):
    source = source_result(tmp_path)
    calls = []
    monkeypatch.setattr(rebuild, 'validate_snapshot', lambda cfg, frame: calls.append(('validate', cfg.result_root, frame)))
    monkeypatch.setattr(rebuild, 'process_batch', lambda cfg, frame, sigmas: calls.append(('compute', cfg.result_root, frame, sigmas)))
    assert rebuild.main(arguments(source, tmp_path / 'new') + ['--execute']) == 0
    assert calls == [('validate', tmp_path / 'new', 7), ('compute', tmp_path / 'new', 7, [15.0])]
