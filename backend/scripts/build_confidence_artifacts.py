#!/usr/bin/env python3
"""Build repo-local backtest and calibration artifacts from an observed-truth registry."""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path


def _install_runtime_stubs() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    app_root = backend_root / "app"
    backend_root_str = str(backend_root)
    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)

    if "app" not in sys.modules:
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = [str(app_root)]
        sys.modules["app"] = app_pkg
    if "app.services" not in sys.modules:
        services_pkg = types.ModuleType("app.services")
        services_pkg.__path__ = [str(app_root / "services")]
        sys.modules["app.services"] = services_pkg


_install_runtime_stubs()

from app.services.backtest_manager import BacktestManager
from app.services.calibration_manager import CalibrationManager


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build backtest_summary.json and calibration_summary.json for one ensemble."
    )
    parser.add_argument("--simulation-id", required=True)
    parser.add_argument("--ensemble-id", required=True)
    parser.add_argument("--simulation-data-dir")
    parser.add_argument(
        "--strict-ready",
        action="store_true",
        help="Exit non-zero unless at least one calibration metric is ready.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    manager_kwargs = {}
    if args.simulation_data_dir:
        manager_kwargs["simulation_data_dir"] = args.simulation_data_dir

    try:
        backtest_manager = BacktestManager(**manager_kwargs)
        calibration_manager = CalibrationManager(**manager_kwargs)
        backtest_summary = backtest_manager.get_backtest_summary(
            args.simulation_id,
            args.ensemble_id,
        )
        calibration_summary = calibration_manager.get_calibration_summary(
            args.simulation_id,
            args.ensemble_id,
        )
    except Exception as exc:  # pragma: no cover - exercised via subprocess tests
        print(f"Failed to build confidence artifacts: {exc}", file=sys.stderr)
        return 1

    ready_metric_ids = calibration_summary.get("quality_summary", {}).get(
        "ready_metric_ids",
        [],
    )
    if args.strict_ready and not ready_metric_ids:
        print(
            "Calibration artifacts built, but the confidence lane is not ready.",
            file=sys.stderr,
        )
        return 2

    print(
        json.dumps(
            {
                "simulation_id": args.simulation_id,
                "ensemble_id": args.ensemble_id,
                "backtest_schema_version": backtest_summary.get("schema_version"),
                "calibration_schema_version": calibration_summary.get(
                    "schema_version"
                ),
                "ready_metric_ids": ready_metric_ids,
                "quality_status": calibration_summary.get("quality_summary", {}).get(
                    "status",
                    "unknown",
                ),
                "evaluation_window_count": backtest_summary.get(
                    "evaluation_summary",
                    {},
                ).get("window_count", 0),
                "benchmark_count": len(
                    backtest_summary.get("evaluation_summary", {}).get(
                        "benchmark_ids",
                        [],
                    )
                ),
                "out_of_sample_case_count": backtest_summary.get(
                    "evaluation_summary",
                    {},
                ).get("out_of_sample_case_count", 0),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
