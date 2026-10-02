"""Rebuild full-domain v7 results from validated inputs into a separate result root."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
from jhtdb_pipeline.config import load_config, RESULT_SCHEMA_VERSION
from jhtdb_pipeline.processing import process_batch, resource_plan
from jhtdb_pipeline.validation import validate_snapshot


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, help='Current v7-compatible YAML pointing at existing velocity inputs')
    parser.add_argument('--source-result', required=True, type=Path, help='Completed v6 or v7 result directory')
    parser.add_argument('--result-root', required=True, type=Path, help='Separate destination root; never the source root')
    parser.add_argument('--execute', action='store_true', help='Validate full input and perform computation; default prints plan only')
    args = parser.parse_args(argv)
    source = args.source_result.resolve()
    payload = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if not (source / 'COMPLETE').is_file() or payload.get('schema_version') not in (6, 7):
        parser.error('source must be a completed v6 or v7 result')
    destination = args.result_root.resolve()
    if destination in source.parents or destination == source or source in destination.parents:
        parser.error('destination must be separate from the source result tree')
    cfg = load_config(args.config)
    if payload.get('dataset') != cfg.dataset:
        parser.error('source dataset does not match configuration')
    cfg = replace(cfg, result_root=destination)
    cfg = cfg.with_filter(payload['filter_type'])
    if cfg.filter_type == 'smooth_sharp':
        cfg = cfg.with_sharp_edge_width_fraction(float(payload['sharp_edge_width_fraction']))
    frame, sigma = int(payload['time_index']), float(payload['sigma_grid'])
    plan = {'source': str(source), 'source_schema': payload['schema_version'],
            'target_schema': RESULT_SCHEMA_VERSION, 'time_index': frame, 'sigma_grid': sigma,
            'destination': str(cfg.result_path(frame, sigma)), 'resources': resource_plan(cfg),
            'mode': 'execute' if args.execute else 'plan',
            'note': 'Recomputes from full validated velocity; never expands a crop or overwrites source.'}
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.execute:
        validate_snapshot(cfg, frame)
        print(process_batch(cfg, frame, [sigma]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
