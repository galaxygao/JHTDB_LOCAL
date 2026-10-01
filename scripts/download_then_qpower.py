"""Durable, sequential download/validation -> preflight -> analysis runner."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from filelock import FileLock
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import field_config
from jhtdb_pipeline.validation import atomic_json


PROJECT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--pipeline-config", default="configs/pipeline.yaml")
    parser.add_argument("--analysis-config", default="qpower_analysis/config.example.json")
    args = parser.parse_args()
    os.chdir(PROJECT)
    job = args.job_dir.resolve()
    job.mkdir(parents=True, exist_ok=False)
    status = {"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat(),
              "status": "running", "stage": "initializing", "completed_stages": []}

    def update(**values):
        status.update(values)
        status["updated_utc"] = datetime.now(timezone.utc).isoformat()
        atomic_json(job / "status.json", status)
        print(json.dumps(status), flush=True)

    try:
        with FileLock(str(PROJECT / "outputs" / "download_then_qpower.lock"), timeout=0):
            cfg = load_config(args.pipeline_config)
            analysis = json.loads(Path(args.analysis_config).read_text(encoding="utf-8"))
            for frame in analysis["frames"]:
                number = int(frame["frame"])
                frame["time"] = cfg.physical_time(number)
                frame["velocity_path"] = str(cfg.raw_store_path(number))
                frame["pressure_gradient_path"] = str(field_config(cfg, "pressure_gradient").raw_store_path(number))
                frame["pressure_gradient_keys"] = ["pressure_gradient"]
            analysis_path = job / "analysis_config.json"
            atomic_json(analysis_path, analysis)
            (job / "pipeline_config.yaml").write_text(Path(args.pipeline_config).read_text(encoding="utf-8"), encoding="utf-8")
            stages = []
            for frame in analysis["frames"]:
                stages.append((f"download_frame_{frame['frame']:06d}", [
                    "-m", "jhtdb_pipeline", "cache", "--field", "pressure_gradient",
                    "--time-index", str(frame["frame"]), "--config", str(job / "pipeline_config.yaml")]))
            analysis_command = [str(PROJECT / "qpower_analysis" / "qpower_analysis.py"),
                                "--config", str(analysis_path)]
            stages.extend([("analysis_preflight", analysis_command + ["--preflight-only"]),
                           ("analysis", analysis_command)])
            for stage, command in stages:
                update(stage=stage, log=str(job / f"{stage}.log"))
                with (job / f"{stage}.log").open("w", encoding="utf-8") as log:
                    result = subprocess.run([sys.executable, "-u", *command], cwd=PROJECT,
                                            stdout=log, stderr=subprocess.STDOUT, check=False)
                if result.returncode:
                    update(status="failed", exit_code=result.returncode)
                    return result.returncode
                status["completed_stages"].append(stage)
            update(status="complete", exit_code=0)
            return 0
    except Exception as exc:
        update(status="failed", error_type=type(exc).__name__, error=str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
