import importlib
import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

for path in (BACKEND_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


_HELPERS_PATH = Path(__file__).with_name("test_probabilistic_operator_flow.py")
_HELPERS_SPEC = importlib.util.spec_from_file_location(
    "_probabilistic_operator_flow_helpers",
    _HELPERS_PATH,
)
_HELPERS = importlib.util.module_from_spec(_HELPERS_SPEC)
assert _HELPERS_SPEC is not None and _HELPERS_SPEC.loader is not None
_HELPERS_SPEC.loader.exec_module(_HELPERS)

from app.models.forecasting import ForecastQuestion
from app.services.forecast_manager import ForecastManager


class _FakeThread:
    def __init__(self, target=None, daemon=None):
        self.target = target
        self.daemon = daemon

    def start(self):
        if self.target:
            self.target()


def _load_report_agent_module():
    return importlib.import_module("app.services.report_agent")


def _load_report_api_module():
    sys.modules.pop("app.api.report", None)
    sys.modules.pop("app.api", None)
    return importlib.import_module("app.api.report")


def test_inference_ready_forecast_flow_persists_completed_probabilistic_report_scope(
    simulation_data_dir,
    forecast_data_dir,
    tmp_path,
    monkeypatch,
    probabilistic_prepare_enabled,
):
    config_module = importlib.import_module("app.config")
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_ENSEMBLE_STORAGE_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "PROBABILISTIC_REPORT_ENABLED",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        config_module.Config,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
        raising=False,
    )

    forecast_manager_module = importlib.import_module("app.services.forecast_manager")
    monkeypatch.setattr(
        forecast_manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    state = _HELPERS._prepare_simulation(simulation_data_dir, monkeypatch)
    manager = ForecastManager(forecast_data_dir=str(forecast_data_dir))
    manager.create_question(
        ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-inference-ready-1",
                "project_id": "proj-1",
                "title": "Inference-ready forecast question",
                "question": (
                    "Will the simulation-backed forecast answer retain extracted "
                    "signals through saved report context?"
                ),
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-07-01"},
                "primary_simulation_id": state.simulation_id,
                "issue_timestamp": "2026-03-31T08:00:00",
                "created_at": "2026-03-31T08:00:00",
                "updated_at": "2026-03-31T08:00:00",
            }
        )
    )

    report_module = _load_report_api_module()
    report_agent_module = _load_report_agent_module()
    client = _HELPERS._build_app_client(monkeypatch)
    simulation_module = _HELPERS._load_simulation_api_module()

    reports_dir = tmp_path / "backend" / "uploads" / "reports"
    monkeypatch.setattr(
        report_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(
        report_agent_module.ReportManager,
        "REPORTS_DIR",
        str(reports_dir),
        raising=False,
    )
    monkeypatch.setattr(report_module.threading, "Thread", _FakeThread)
    monkeypatch.setattr(
        report_module.ProjectManager,
        "get_project",
        lambda _project_id: type(
            "Project",
            (),
            {
                "graph_id": "graph-1",
                "simulation_requirement": "Forecast discussion spread",
            },
        )(),
        raising=False,
    )

    def _fake_start_simulation(**kwargs):
        return _HELPERS._FakeRunState(
            kwargs["simulation_id"],
            ensemble_id=kwargs["ensemble_id"],
            run_id=kwargs["run_id"],
            runner_status="running",
        )

    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "start_simulation",
        _fake_start_simulation,
        raising=False,
    )
    monkeypatch.setattr(
        simulation_module.SimulationRunner,
        "get_run_state",
        lambda simulation_id, ensemble_id=None, run_id=None: None,
        raising=False,
    )

    class _FakeReportAgent:
        def __init__(
            self,
            *,
            graph_id,
            simulation_id,
            simulation_requirement,
            probabilistic_context=None,
            base_graph_id=None,
            runtime_graph_id=None,
            graph_ids=None,
        ):
            self.graph_id = graph_id
            self.base_graph_id = base_graph_id
            self.runtime_graph_id = runtime_graph_id
            self.graph_ids = graph_ids or []
            self.simulation_id = simulation_id
            self.simulation_requirement = simulation_requirement
            self.probabilistic_context = probabilistic_context

        def generate_report(self, progress_callback=None, report_id=None):
            if progress_callback is not None:
                progress_callback("planning", 20, "Building bounded report outline")
                progress_callback("drafting", 80, "Persisting scoped report payload")
            return report_agent_module.Report(
                report_id=report_id or "report-inference-ready-proof",
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                base_graph_id=self.base_graph_id,
                runtime_graph_id=self.runtime_graph_id,
                graph_ids=self.graph_ids,
                simulation_requirement=self.simulation_requirement,
                status=report_agent_module.ReportStatus.COMPLETED,
                markdown_content="# Integration proof\n",
                created_at="2026-03-31T09:30:00",
                completed_at="2026-03-31T09:35:00",
                probabilistic_context=self.probabilistic_context,
            )

    monkeypatch.setattr(report_module, "ReportAgent", _FakeReportAgent)

    create_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles",
        json={
            "run_count": 1,
            "max_concurrency": 1,
            "root_seed": 431,
            "forecast_id": "forecast-inference-ready-1",
        },
    )
    assert create_response.status_code == 200
    ensemble_payload = create_response.get_json()["data"]
    ensemble_id = ensemble_payload["ensemble_id"]
    run_path = Path(ensemble_payload["runs"][0]["path"])

    manifest_path = run_path / "run_manifest.json"
    resolved_config_path = run_path / "resolved_config.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    resolved_payload = json.loads(resolved_config_path.read_text(encoding="utf-8"))
    manifest_payload["base_graph_id"] = "graph-1"
    manifest_payload["runtime_graph_id"] = "runtime-graph-1"
    manifest_payload["graph_id"] = "graph-1"
    resolved_payload["base_graph_id"] = "graph-1"
    resolved_payload["runtime_graph_id"] = "runtime-graph-1"
    resolved_payload["graph_id"] = "graph-1"
    manifest_path.write_text(
        json.dumps(manifest_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    resolved_config_path.write_text(
        json.dumps(resolved_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    start_response = client.post(
        f"/api/simulation/{state.simulation_id}/ensembles/{ensemble_id}/runs/0001/start",
        json={"platform": "parallel", "forecast_id": "forecast-inference-ready-1"},
    )
    assert start_response.status_code == 200

    _HELPERS._write_json(
        run_path / "run_state.json",
        {
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
            "run_key": f"{state.simulation_id}::{ensemble_id}::0001",
            "run_dir": str(run_path),
            "config_path": str(run_path / "resolved_config.json"),
            "platform_mode": "parallel",
            "runner_status": "completed",
            "started_at": "2026-03-31T09:10:00",
            "updated_at": "2026-03-31T09:20:00",
            "completed_at": "2026-03-31T09:20:00",
        },
    )
    _HELPERS._write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "status": "completed",
        },
    )
    (run_path / "twitter").mkdir(parents=True, exist_ok=True)
    (run_path / "twitter" / "actions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "round": 1,
                        "timestamp": "2026-03-31T09:12:00",
                        "platform": "twitter",
                        "agent_id": 1,
                        "agent_name": "Analyst A",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "The simulated market leans above fifty-fifty.",
                            "forecast_probability": 0.58,
                            "confidence": 0.6,
                            "rationale_tags": ["base_rate"],
                        },
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round": 2,
                        "timestamp": "2026-03-31T09:15:00",
                        "platform": "twitter",
                        "agent_id": 2,
                        "agent_name": "Analyst B",
                        "action_type": "CREATE_POST",
                        "action_args": {
                            "content": "There is still some downside uncertainty in the scenario mix.",
                            "forecast_probability": "48%",
                            "confidence": "low",
                            "rationale_tags": ["risk"],
                            "missing_information_requests": ["Need more policy detail"],
                        },
                        "success": True,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    extractor_module = _HELPERS._load_simulation_market_extractor_module()
    extractor = extractor_module.SimulationMarketExtractor(
        simulation_data_dir=str(simulation_data_dir),
        forecast_data_dir=str(forecast_data_dir),
    )
    persisted = extractor.persist_run_market_artifacts(
        state.simulation_id,
        ensemble_id=ensemble_id,
        run_id="0001",
        run_dir=str(run_path),
    )
    _HELPERS._write_json(
        run_path / "run_manifest.json",
        {
            **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")),
            "artifact_paths": {
                **json.loads((run_path / "run_manifest.json").read_text(encoding="utf-8")).get(
                    "artifact_paths",
                    {},
                ),
                "simulation_market_manifest": "simulation_market_manifest.json",
                "agent_belief_book": "agent_belief_book.json",
                "belief_update_trace": "belief_update_trace.json",
                "disagreement_summary": "disagreement_summary.json",
                "market_snapshot": "market_snapshot.json",
                "argument_map": "argument_map.json",
                "missing_information_signals": "missing_information_signals.json",
            },
        },
    )

    assert persisted["manifest"]["extraction_status"] == "ready"
    report_context_path = run_path.parent.parent / "probabilistic_report_context.json"

    manager.attach_simulation_scope(
        "forecast-inference-ready-1",
        simulation_id=state.simulation_id,
        ensemble_ids=[ensemble_id],
        run_ids=["0001"],
        latest_ensemble_id=ensemble_id,
        latest_run_id="0001",
        source_stage="integration_test",
    )
    workspace = manager.generate_hybrid_forecast_answer(
        "forecast-inference-ready-1",
        requested_at="2026-03-31T09:25:00",
    )
    answer = workspace.forecast_answers[-1]

    generate_response = client.post(
        "/api/report/generate",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
            "force_regenerate": True,
        },
    )
    assert generate_response.status_code == 200, generate_response.get_data(as_text=True)
    generate_payload = generate_response.get_json()["data"]
    report_id = generate_payload["report_id"]
    task_id = generate_payload["task_id"]

    status_response = client.post(
        "/api/report/generate/status",
        json={"task_id": task_id},
    )
    assert status_response.status_code == 200
    assert status_response.get_json()["data"]["status"] == "completed"

    report_response = client.get(f"/api/report/{report_id}")
    assert report_response.status_code == 200, report_response.get_data(as_text=True)
    report_payload = report_response.get_json()["data"]
    probabilistic_context = report_payload["probabilistic_context"]
    assert report_context_path.exists()
    report_context_artifact = json.loads(report_context_path.read_text(encoding="utf-8"))

    assert report_payload["status"] == "completed"
    assert report_payload["ensemble_id"] == ensemble_id
    assert report_payload["run_id"] == "0001"
    assert report_context_artifact["ensemble_id"] == ensemble_id
    assert report_context_artifact["run_id"] == "0001"
    assert report_context_artifact["scope"]["ensemble_id"] == ensemble_id
    assert report_context_artifact["scope"]["run_id"] == "0001"
    assert probabilistic_context["scope"]["ensemble_id"] == ensemble_id
    assert probabilistic_context["scope"]["run_id"] == "0001"
    assert probabilistic_context["selected_run"]["run_id"] == "0001"
    assert probabilistic_context["forecast_workspace"]["forecast_question"]["forecast_id"] == (
        "forecast-inference-ready-1"
    )
    assert probabilistic_context["forecast_workspace"]["forecast_question"]["question_text"] == (
        "Will the simulation-backed forecast answer retain extracted signals through saved report context?"
    )
    assert probabilistic_context["forecast_workspace"]["prediction_ledger"]["entry_count"] == 1
    assert probabilistic_context["forecast_workspace"]["forecast_answer"]["answer_type"] == (
        "hybrid_forecast"
    )
    assert probabilistic_context["forecast_workspace"]["forecast_answer"]["answer_id"] == (
        answer.answer_id
    )
    assert probabilistic_context["forecast_workspace"]["forecast_answer"]["answer_payload"][
        "best_estimate"
    ] is not None
    assert round(
        probabilistic_context["selected_run"]["simulation_market"]["market_snapshot"][
            "synthetic_consensus_probability"
        ],
        2,
    ) == 0.53
    assert probabilistic_context["signal_provenance_summary"]["status"] == "partial"
    assert probabilistic_context["forecast_object"]["latest_answer_id"] == answer.answer_id

    exact_scope_status_response = client.post(
        "/api/report/generate/status",
        json={
            "simulation_id": state.simulation_id,
            "ensemble_id": ensemble_id,
            "run_id": "0001",
        },
    )
    assert exact_scope_status_response.status_code == 200
    exact_scope_payload = exact_scope_status_response.get_json()["data"]
    assert exact_scope_payload["already_completed"] is True
    assert exact_scope_payload["report_id"] == report_id
