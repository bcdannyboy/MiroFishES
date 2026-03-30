import sys
import types
from enum import Enum
from pathlib import Path

from flask import Blueprint
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (BACKEND_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _install_test_stubs() -> None:
    """Provide lightweight stand-ins for optional runtime dependencies."""
    if "flask_cors" not in sys.modules:
        flask_cors = types.ModuleType("flask_cors")

        def cors_stub(*_args, **_kwargs):
            return None

        flask_cors.CORS = cors_stub
        sys.modules["flask_cors"] = flask_cors

    if "openai" not in sys.modules:
        openai = types.ModuleType("openai")

        class OpenAI:  # pragma: no cover - trivial stub
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        openai.OpenAI = OpenAI
        sys.modules["openai"] = openai

    if "zep_cloud" not in sys.modules:
        zep_cloud = types.ModuleType("zep_cloud")
        zep_client = types.ModuleType("zep_cloud.client")

        class Zep:  # pragma: no cover - trivial stub
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class EpisodeData:  # pragma: no cover - trivial stub
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class EntityEdgeSourceTarget:  # pragma: no cover - trivial stub
            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        class InternalServerError(Exception):
            pass

        zep_client.Zep = Zep
        zep_cloud.EpisodeData = EpisodeData
        zep_cloud.EntityEdgeSourceTarget = EntityEdgeSourceTarget
        zep_cloud.InternalServerError = InternalServerError
        zep_cloud.client = zep_client
        sys.modules["zep_cloud"] = zep_cloud
        sys.modules["zep_cloud.client"] = zep_client

    if "app.services.simulation_runner" not in sys.modules:
        simulation_runner = types.ModuleType("app.services.simulation_runner")

        class RunnerStatus(str, Enum):
            IDLE = "idle"
            RUNNING = "running"
            COMPLETED = "completed"

        class SimulationRunner:  # pragma: no cover - trivial stub
            @classmethod
            def get_run_state(cls, _simulation_id):
                return None

        simulation_runner.RunnerStatus = RunnerStatus
        simulation_runner.SimulationRunner = SimulationRunner
        sys.modules["app.services.simulation_runner"] = simulation_runner

    if "app.services" not in sys.modules:
        services_pkg = types.ModuleType("app.services")
        services_pkg.__path__ = [str(BACKEND_ROOT / "app" / "services")]
        sys.modules["app.services"] = services_pkg

    if "app.api" not in sys.modules:
        api_pkg = types.ModuleType("app.api")
        api_pkg.__path__ = [str(BACKEND_ROOT / "app" / "api")]
        api_pkg.graph_bp = Blueprint("graph", __name__)
        api_pkg.simulation_bp = Blueprint("simulation", __name__)
        api_pkg.report_bp = Blueprint("report", __name__)
        api_pkg.forecast_bp = Blueprint("forecast", __name__)
        sys.modules["app.api"] = api_pkg

    for module_name in ("app.api.graph", "app.api.report"):
        if module_name not in sys.modules:
            sys.modules[module_name] = types.ModuleType(module_name)


_install_test_stubs()


@pytest.fixture
def simulation_data_dir(tmp_path, monkeypatch):
    """Provide an isolated simulation artifact root for each test."""
    data_dir = tmp_path / "simulations"
    data_dir.mkdir(parents=True, exist_ok=True)

    from app.config import Config

    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(data_dir), raising=False)
    return data_dir


@pytest.fixture
def forecast_data_dir(tmp_path, monkeypatch):
    """Provide an isolated forecast artifact root for each test."""
    data_dir = tmp_path / "forecasts"
    data_dir.mkdir(parents=True, exist_ok=True)

    from app.config import Config

    monkeypatch.setattr(Config, "FORECAST_DATA_DIR", str(data_dir), raising=False)
    return data_dir


@pytest.fixture
def probabilistic_domain():
    """Canonical probabilistic input domain used across backend tests."""
    from app.models.probabilistic import (
        DEFAULT_OUTCOME_METRICS,
        SUPPORTED_OUTCOME_METRIC_DEFINITIONS,
    )

    return {
        "profiles": [
            "deterministic-baseline",
            "balanced",
            "stress-test",
        ],
        "default_profile": "deterministic-baseline",
        "metrics": dict(SUPPORTED_OUTCOME_METRIC_DEFINITIONS),
        "default_metrics": list(DEFAULT_OUTCOME_METRICS),
        "seed_policy": {
            "strategy": "deterministic-root",
            "root_seed": 0,
            "derive_run_seeds": True,
        },
    }


@pytest.fixture
def probabilistic_prepare_enabled(monkeypatch):
    """Enable probabilistic prepare explicitly for API tests."""
    from app.config import Config

    monkeypatch.setattr(Config, "PROBABILISTIC_PREPARE_ENABLED", True, raising=False)
    return True
