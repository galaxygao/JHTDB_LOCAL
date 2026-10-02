"""Shared Windows/macOS bootstrap and download entry point (standard library only)."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv


PROJECT = Path(__file__).resolve().parent


def environment_python(system: str) -> Path:
    name = {"win32": "windows", "darwin": "mac"}.get(system, "linux")
    root = PROJECT / f".venv-{name}"
    return root / ("Scripts/python.exe" if system == "win32" else "bin/python")


def run(command, *, keep_awake=False):
    command = [str(value) for value in command]
    if keep_awake and sys.platform == "darwin":
        command = ["/usr/bin/caffeinate", "-i", *command]
    subprocess.run(command, cwd=PROJECT, check=True)


def prepare_config(python: Path, data_root: Path, token_file: Path) -> Path:
    """Derive a local config without editing the shared production YAML."""
    config = data_root / "pipeline.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    # PyYAML is available in the project environment after bootstrap.
    script = """
import pathlib, sys, yaml
source, destination, root, token = map(pathlib.Path, sys.argv[1:])
data = yaml.safe_load(source.read_text(encoding='utf-8'))
data['platform'] = {key + '_root': str(root / folder) for key, folder in
                    [('state', 'state'), ('run', 'runs'), ('result', 'results')]}
data['auth']['token_file'] = str(token)
destination.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
"""
    run([python, "-c", script, PROJECT / "configs/pipeline.yaml", config, data_root, token_file])
    return config


def pipeline_commands(python: Path, config: Path, time_index: int, stage: str):
    base = [python, "-m", "jhtdb_pipeline"]
    frame = ["--time-index", str(time_index), "--config", config]
    if stage == "check":
        return [base + ["doctor", *frame]]
    # cache already verifies checksums and validates each complete field.
    commands = [base + ["doctor", *frame], base + ["smoke", "--field", "velocity", *frame],
                base + ["cache", *frame]]
    if stage != "velocity":
        commands.append([python, "-m", "jhtdb_pipeline.pressure_local", "--stage", "all" if stage == "all" else "download", *frame])
    return commands


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("setup", "check", "velocity", "download", "qpower", "all"), default="all")
    parser.add_argument("--time-index", type=int, default=1)
    parser.add_argument("--data-root", type=Path, default=PROJECT / ".local")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--skip-install", action="store_true", help="Reuse the installed local environment")
    parser.add_argument("--background", action="store_true", help="Continue independently of the terminal; write deploy.log")
    parser.add_argument("--wait-lock", action="store_true", help="Wait for another deployment using the same data root")
    args = parser.parse_args(argv)
    if args.time_index < 1:
        parser.error("--time-index must be >= 1")
    root = args.data_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.background:
        arguments = [arg for arg in (sys.argv[1:] if argv is None else argv) if arg != "--background"]
        command = [sys.executable, "-u", str(PROJECT / "deploy.py"), *arguments]
        options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
                   if sys.platform == "win32" else {"start_new_session": True})
        with (root / "deploy.log").open("a", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=PROJECT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, **options)
        (root / "deploy.pid").write_text(str(process.pid), encoding="utf-8")
        print(f"Started PID {process.pid}; log: {root / 'deploy.log'}")
        return 0
    python = environment_python(sys.platform)
    if not python.is_file():
        if args.skip_install:
            parser.error("Local environment is missing; omit --skip-install")
        venv.EnvBuilder(with_pip=True).create(python.parent.parent)
    if not args.skip_install:
        run([python, "-m", "pip", "install", "--editable", f"{PROJECT}[dev]"])
        run([python, "-m", "pip", "check"])
    os.environ.setdefault("MPLCONFIGDIR", str(root / "cache/matplotlib"))
    token = args.token_file
    if token is None:
        local_token = PROJECT / ".secrets/jhtdb_token"
        token = local_token if local_token.is_file() else Path.home() / ".secrets/jhtdb_token"
    # One deployment per local data root. The existing downloader also takes its
    # own request lock; this covers the smoke/check/analysis sequence as well.
    lock_script = """
import os, subprocess, sys
from filelock import FileLock
with FileLock(sys.argv[1], timeout=float(sys.argv[2])):
    result = subprocess.run(sys.argv[3:], env={**os.environ, 'JHTDB_DEPLOY_LOCKED': '1'})
    raise SystemExit(result.returncode)
"""
    if os.environ.get("JHTDB_DEPLOY_LOCKED") != "1":
        child = [python, PROJECT / "deploy.py", *(sys.argv[1:] if argv is None else argv)]
        if "--skip-install" not in child:
            child.append("--skip-install")
        run([python, "-c", lock_script, root / "deploy.lock", -1 if args.wait_lock else 0, *child], keep_awake=True)
        return 0
    config = prepare_config(python, root, token.expanduser().resolve())
    print(f"Environment: {python}\nLocal config: {config}", flush=True)
    if args.stage == "setup":
        return 0
    if args.stage in ("check", "velocity", "download", "all"):
        for command in pipeline_commands(python, config, args.time_index, args.stage):
            run(command)
    if args.stage in ("qpower", "all"):
        run([python, "-m", "jhtdb_pipeline.pressure_local", "--stage", "gradient",
             "--time-index", args.time_index, "--config", config])
        analysis = json.loads((PROJECT / "qpower_analysis/config.example.json").read_text(encoding="utf-8"))
        frame = analysis["frames"][0]
        inputs = root / "state/inputs" / f"t{args.time_index:06d}"
        frame.update(frame=args.time_index, velocity_path=str(inputs / "velocity_cache.zarr"),
                     pressure_gradient_path=str(inputs / "pressure_gradient_fd4_cache.zarr"))
        # Derive physical time from the unchanged source config, not a duplicate constant.
        run([python, "-c", "from jhtdb_pipeline.config import load_config; import json,sys; "
             "a=json.loads(sys.argv[3]); a['frames'][0]['time']=load_config(sys.argv[1]).physical_time(int(sys.argv[2])); "
             "from pathlib import Path; Path(sys.argv[4]).write_text(json.dumps(a,indent=2),encoding='utf-8')",
             config, args.time_index, json.dumps({**analysis, "output_root": str(PROJECT / "qpower_analysis/output")}),
             root / "qpower.json"])
        command = [python, PROJECT / "qpower_analysis/qpower_analysis.py", "--config", root / "qpower.json"]
        run([*command, "--preflight-only"])
        run(command)
    print(f"Completed stage: {args.stage}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Stage failed (exit {exc.returncode}); subsequent stages were not run.", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except KeyboardInterrupt:
        raise SystemExit(130)
