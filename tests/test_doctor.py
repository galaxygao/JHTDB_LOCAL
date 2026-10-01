from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.doctor import ensure_run_record


class DoctorTests(unittest.TestCase):
    def test_local_run_record_never_expires(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cfg = replace(
                load_config("configs/pipeline.yaml"),
                run_root=root / "runs",
                state_root=root / "state",
                result_root=root / "results",
            )
            record = ensure_run_record(cfg, 1)
            self.assertIsNone(record["expires_at"])
            self.assertEqual(ensure_run_record(cfg, 1), record)


if __name__ == "__main__":
    unittest.main()
