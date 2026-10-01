from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from jhtdb_pipeline.cli import _run_single_frame, _selected_sigmas, build_parser, main


class CliBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = SimpleNamespace(sigma_grids=(1.0, 2.0, 3.0))

    def test_configured_sigmas_are_selected_without_override(self) -> None:
        self.assertEqual(_selected_sigmas(self.cfg, None), (1.0, 2.0, 3.0))
        self.assertEqual(_selected_sigmas(self.cfg, 2.5), (2.5,))

    def test_upgrade_result_accepts_frame_and_sigma(self) -> None:
        args = build_parser().parse_args(
            ["upgrade-result", "--time-index", "7", "--sigma-grid", "2.0"]
        )
        self.assertEqual(args.command, "upgrade-result")
        self.assertEqual(args.time_index, 7)
        self.assertEqual(args.sigma_grid, 2.0)

    def test_backfill_and_sbar_qa_commands_accept_frame_and_sigma(self) -> None:
        for command in (
            "backfill-full-fields",
            "backfill-full-regime",
            "compute-cq",
            "compute-weak-asymmetry",
            "qa-sbar",
        ):
            args = build_parser().parse_args(
                [command, "--time-index", "7", "--sigma-grid", "2.0"]
            )
            self.assertEqual(args.command, command)
            self.assertEqual(args.time_index, 7)
            self.assertEqual(args.sigma_grid, 2.0)

    def test_processing_commands_accept_smooth_sharp_filter(self) -> None:
        args = build_parser().parse_args(
            [
                "process-batch",
                "--time-index",
                "1",
                "--sigma-grid",
                "10",
                "--filter-type",
                "smooth_sharp",
            ]
        )
        self.assertEqual(args.filter_type, "smooth_sharp")

    def test_process_batch_accepts_multiple_sigma_values(self) -> None:
        args = build_parser().parse_args(
            [
                "process-batch",
                "--time-index",
                "1",
                "--sigma-grids",
                "5",
                "10",
                "20",
                "--filter-type",
                "smooth_sharp",
            ]
        )
        self.assertEqual(args.sigma_grids, [5.0, 10.0, 20.0])

    def test_smooth_sharp_accepts_scale_invariant_edge_width(self) -> None:
        args = build_parser().parse_args(
            [
                "process-batch",
                "--time-index",
                "1",
                "--sigma-grids",
                "10",
                "30",
                "75",
                "--filter-type",
                "smooth_sharp",
                "--sharp-edge-width-fraction",
                "0.1171875",
            ]
        )
        self.assertEqual(args.sharp_edge_width_fraction, 0.1171875)

    @patch("jhtdb_pipeline.cli.subprocess.run")
    @patch("jhtdb_pipeline.cli.load_config")
    def test_gui_uses_local_browser_address_without_telemetry(
        self, load_config, run
    ) -> None:
        load_config.return_value = self.cfg
        run.return_value.returncode = 0

        result = main(["gui", "--port", "8502", "--config", "test.yaml"])

        self.assertEqual(result, 0)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--server.address") + 1], "127.0.0.1")
        self.assertEqual(command[command.index("--server.port") + 1], "8502")
        self.assertEqual(
            command[command.index("--browser.gatherUsageStats") + 1], "false"
        )

    @patch("jhtdb_pipeline.cli.process_batch")
    @patch("jhtdb_pipeline.cli.validate_snapshot")
    @patch("jhtdb_pipeline.cli.fetch_snapshot")
    @patch("jhtdb_pipeline.cli.doctor")
    @patch("jhtdb_pipeline.cli.reuse_or_backfill_result")
    def test_single_frame_fetches_once_and_processes_each_sigma(
        self, reuse, doctor, fetch, validate, process_batch
    ) -> None:
        reuse.return_value = None
        doctor.return_value = {"status": "ok"}
        process_batch.return_value = [
            Path("result_sigma_1"),
            Path("result_sigma_2"),
            Path("result_sigma_3"),
        ]

        results = _run_single_frame(self.cfg, 1, None)

        doctor.assert_called_once_with(self.cfg, 1)
        fetch.assert_called_once_with(self.cfg, 1)
        validate.assert_called_once_with(self.cfg, 1)
        process_batch.assert_called_once_with(
            self.cfg, 1, (1.0, 2.0, 3.0)
        )
        self.assertEqual(
            results,
            [Path("result_sigma_1"), Path("result_sigma_2"), Path("result_sigma_3")],
        )

    @patch("jhtdb_pipeline.cli.validate_snapshot")
    @patch("jhtdb_pipeline.cli.fetch_snapshot")
    @patch("jhtdb_pipeline.cli.doctor")
    @patch("jhtdb_pipeline.cli.reuse_or_backfill_result")
    def test_single_frame_fast_upgrades_existing_results_without_fetch(
        self, reuse, doctor, fetch, validate
    ) -> None:
        reuse.side_effect = lambda cfg, frame, sigma: Path(
            f"upgraded_sigma_{sigma:g}"
        )

        results = _run_single_frame(self.cfg, 1, None)

        doctor.assert_not_called()
        fetch.assert_not_called()
        validate.assert_not_called()
        self.assertEqual(
            results,
            [
                Path("upgraded_sigma_1"),
                Path("upgraded_sigma_2"),
                Path("upgraded_sigma_3"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
