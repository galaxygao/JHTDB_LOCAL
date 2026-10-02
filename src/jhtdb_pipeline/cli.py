from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from .auth import has_token, token_source
from .catalog import Catalog
from .config import FILTER_TYPES, load_config
from .cq import run_cq
from .doctor import doctor
from .jhtdb import fetch_snapshot, smoke
from .input_fields import field_config
from .planning import plan
from .regime_pi import run_regime_pi_statistics
from .processing import (
    finalize_result,
    process_batch,
    process_full,
    resource_plan,
    reuse_complete_result,
)
from .sbar_qa import run_sbar_qa
from .validation import validate_snapshot
from .weak_asymmetry import run_weak_asymmetry


DEFAULT_CONFIG = "configs/pipeline.yaml"


def _config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default=DEFAULT_CONFIG)


def _frame(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--time-index", type=int, required=True)
    _config(parser)


def _sigma(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sigma-grid", type=float)
    parser.add_argument(
        "--filter-type",
        choices=FILTER_TYPES,
        help="override physics.filter_type for this command",
    )
    parser.add_argument(
        "--sharp-edge-width-fraction",
        type=float,
        help="set the smooth-sharp width alpha=w/k_c",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local JHTDB periodic-domain pipeline"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    auth_parser = commands.add_parser("auth", help="report JHTDB token status")
    auth_parser.add_argument("action", choices=("status",))
    _config(auth_parser)

    doctor_parser = commands.add_parser("doctor", help="check local environment")
    doctor_parser.add_argument("--time-index", type=int)
    _config(doctor_parser)

    for name in ("plan", "smoke", "cache", "validate-input", "status"):
        command = commands.add_parser(name)
        command.add_argument("--field", choices=("velocity", "pressure_gradient"), default="velocity")
        if name == "cache":
            command.add_argument("--with-pressure-gradient", action="store_true")
        if name != "status":
            _frame(command)
        else:
            _config(command)

    for name in (
        "process-full",
        "process-batch",
        "finalize-result",
        "single-frame",
        "compute-cq",
        "compute-weak-asymmetry",
        "compute-regime-pi",
        "qa-sbar",
    ):
        command = commands.add_parser(name)
        _frame(command)
        _sigma(command)
        if name == "single-frame":
            command.add_argument("--with-pressure-gradient", action="store_true")
        if name in ("process-batch", "single-frame", "compute-regime-pi"):
            command.add_argument(
                "--sigma-grids",
                type=float,
                nargs="+",
                metavar="SIGMA",
                help=(
                    "compute these sigma values sequentially"
                    if name == "compute-regime-pi"
                    else "process these sigma values in one shared-FFT batch"
                ),
            )

    gui = commands.add_parser("gui", help="start the read-only server GUI")
    gui.add_argument("--port", type=int, default=8501)
    _config(gui)

    return parser


def _status(cfg) -> dict[str, object]:
    inputs: list[dict[str, object]] = []
    if cfg.catalog_path.exists():
        with Catalog(cfg.catalog_path) as catalog:
            for row in catalog.snapshots(cfg.dataset):
                item = dict(row)
                item["tiles"] = catalog.tile_progress(cfg.dataset, row["time_index"])
                inputs.append(item)
    results: list[dict[str, object]] = []
    filter_batches: list[dict[str, object]] = []
    if cfg.result_root.exists():
        for path in sorted(cfg.result_root.iterdir()):
            if (
                not path.is_dir()
                or path.name.startswith(".")
                or path.name.endswith("_shared")
            ):
                continue
            manifest_path = path / "manifest.json"
            complete = (path / "COMPLETE").is_file()
            item: dict[str, object] = {"result_id": path.name, "complete": complete}
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                item.update(
                    {
                        "time_index": manifest.get("time_index"),
                        "sigma_grid": manifest.get("sigma_grid"),
                        "filter_type": manifest.get("filter_type", "gaussian"),
                        "manifest_status": manifest.get("status"),
                        "schema_version": manifest.get("schema_version"),
                        "s_bar_qa_passed": manifest.get("s_bar_qa_passed"),
                        "cq_passed": manifest.get("cq_passed"),
                        "weak_asymmetry_passed": manifest.get(
                            "weak_asymmetry_passed"
                        ),
                    }
                )
            results.append(item)
        for path in sorted(cfg.result_root.glob("t*_filter_*_batch_manifest.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload["manifest_path"] = str(path)
                filter_batches.append(payload)
            except (OSError, ValueError, json.JSONDecodeError):
                filter_batches.append(
                    {"manifest_path": str(path), "status": "invalid"}
                )
    pressure_inputs = []
    if cfg.variable == "velocity":
        pressure_cfg = field_config(cfg, "pressure_gradient")
        if pressure_cfg.catalog_path.exists():
            with Catalog(pressure_cfg.catalog_path) as catalog:
                for row in catalog.snapshots(cfg.dataset):
                    item = dict(row)
                    item["tiles"] = catalog.tile_progress(cfg.dataset, row["time_index"])
                    pressure_inputs.append(item)
    return {"field": cfg.variable, "inputs": inputs, "pressure_gradient_inputs": pressure_inputs,
            "results": results, "filter_batches": filter_batches}


def _selected_sigmas(cfg, sigma_grid: float | None) -> tuple[float, ...]:
    return (float(sigma_grid),) if sigma_grid is not None else cfg.sigma_grids


def _run_single_frame(
    cfg,
    time_index: int,
    sigma_grid: float | None,
    sigma_grids: list[float] | None = None,
) -> list[Path]:
    if sigma_grid is not None and sigma_grids:
        raise ValueError("use only one of --sigma-grid and --sigma-grids")
    sigmas = (
        tuple(float(value) for value in sigma_grids)
        if sigma_grids
        else _selected_sigmas(cfg, sigma_grid)
    )
    results: dict[float, Path] = {}
    pending = []
    for sigma in sigmas:
        existing = reuse_complete_result(cfg, time_index, sigma)
        if existing is None:
            pending.append(sigma)
        else:
            results[sigma] = existing
    if not pending:
        return [results[sigma] for sigma in sigmas]

    report = doctor(cfg, time_index)
    if report["status"] != "ok":
        raise RuntimeError(f"local doctor failed: {json.dumps(report['checks'])}")
    fetch_snapshot(cfg, time_index)
    validate_snapshot(cfg, time_index)
    return process_batch(cfg, time_index, sigmas)


def _print_paths(paths: list[Path]) -> None:
    if len(paths) == 1:
        print(paths[0])
    else:
        print(json.dumps([str(path) for path in paths], ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, OSError):
                pass
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        cfg = field_config(cfg, getattr(args, "field", "velocity"))
        selected_filter = getattr(args, "filter_type", None)
        if selected_filter is not None:
            cfg = cfg.with_filter(selected_filter)
        selected_edge_fraction = getattr(args, "sharp_edge_width_fraction", None)
        if selected_edge_fraction is not None:
            cfg = cfg.with_sharp_edge_width_fraction(selected_edge_fraction)
        if args.command == "auth":
            print(
                json.dumps(
                    {
                        "configured": has_token(cfg),
                        "source": token_source(cfg),
                    }
                )
            )
        elif args.command == "doctor":
            report = doctor(cfg, args.time_index)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["status"] == "ok" else 2
        elif args.command == "plan":
            payload = plan(cfg, args.time_index)
            payload["resources"] = resource_plan(cfg)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.command == "smoke":
            print(json.dumps(smoke(cfg, args.time_index), ensure_ascii=False, indent=2))
        elif args.command == "cache":
            print(fetch_snapshot(cfg, args.time_index))
            if args.with_pressure_gradient and args.field == "velocity":
                print(fetch_snapshot(field_config(cfg, "pressure_gradient"), args.time_index))
        elif args.command == "validate-input":
            print(
                json.dumps(
                    validate_snapshot(cfg, args.time_index),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        elif args.command == "process-full":
            _print_paths(
                [
                    process_full(cfg, args.time_index, sigma)
                    for sigma in _selected_sigmas(cfg, args.sigma_grid)
                ]
            )
        elif args.command == "finalize-result":
            _print_paths(
                [
                    finalize_result(cfg, args.time_index, sigma)
                    for sigma in _selected_sigmas(cfg, args.sigma_grid)
                ]
            )
        elif args.command == "compute-cq":
            reports = [
                run_cq(cfg, args.time_index, sigma)
                for sigma in _selected_sigmas(cfg, args.sigma_grid)
            ]
            print(
                json.dumps(
                    reports[0] if len(reports) == 1 else reports,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if all(report["passed"] for report in reports) else 2
        elif args.command == "compute-weak-asymmetry":
            reports = [
                run_weak_asymmetry(cfg, args.time_index, sigma)
                for sigma in _selected_sigmas(cfg, args.sigma_grid)
            ]
            print(
                json.dumps(
                    reports[0] if len(reports) == 1 else reports,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if all(report["passed"] for report in reports) else 2
        elif args.command == "qa-sbar":
            reports = [
                run_sbar_qa(cfg, args.time_index, sigma)
                for sigma in _selected_sigmas(cfg, args.sigma_grid)
            ]
            print(
                json.dumps(
                    reports[0] if len(reports) == 1 else reports,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0 if all(report["passed"] for report in reports) else 2
        elif args.command == "compute-regime-pi":
            if args.sigma_grid is not None and args.sigma_grids:
                raise ValueError("use only one of --sigma-grid and --sigma-grids")
            sigmas = (
                tuple(float(value) for value in args.sigma_grids)
                if args.sigma_grids
                else _selected_sigmas(cfg, args.sigma_grid)
            )
            _print_paths(
                [
                    run_regime_pi_statistics(cfg, args.time_index, sigma)
                    for sigma in sigmas
                ]
            )
        elif args.command == "process-batch":
            if args.sigma_grid is not None and args.sigma_grids:
                raise ValueError("use only one of --sigma-grid and --sigma-grids")
            sigmas = (
                tuple(float(value) for value in args.sigma_grids)
                if args.sigma_grids
                else _selected_sigmas(cfg, args.sigma_grid)
            )
            _print_paths(
                process_batch(
                    cfg,
                    args.time_index,
                    sigmas,
                )
            )
        elif args.command == "single-frame":
            if args.with_pressure_gradient:
                fetch_snapshot(field_config(cfg, "pressure_gradient"), args.time_index)
            _print_paths(
                _run_single_frame(
                    cfg, args.time_index, args.sigma_grid, args.sigma_grids
                )
            )
        elif args.command == "status":
            print(json.dumps(_status(cfg), ensure_ascii=False, indent=2))
        elif args.command == "gui":
            environment = os.environ.copy()
            environment["JHTDB_PIPELINE_CONFIG"] = str(Path(args.config).resolve())
            dashboard = Path(__file__).with_name("dashboard.py")
            command = [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(dashboard),
                "--server.address",
                "127.0.0.1",
                "--server.port",
                str(args.port),
                "--browser.gatherUsageStats",
                "false",
            ]
            return subprocess.run(command, env=environment, check=False).returncode
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
