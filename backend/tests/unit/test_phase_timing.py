import importlib
import importlib.util
import json
from pathlib import Path


def _load_phase_timing_module():
    spec = importlib.util.find_spec("app.services.phase_timing")
    assert spec is not None, "app.services.phase_timing must exist"
    return importlib.import_module("app.services.phase_timing")


def test_phase_timing_recorder_persists_stable_contract_and_merges_phases(tmp_path):
    module = _load_phase_timing_module()
    artifact_path = tmp_path / "graph_phase_timings.json"
    recorder = module.PhaseTimingRecorder(
        artifact_path=str(artifact_path),
        scope_kind="project",
        scope_id="proj_test",
    )

    first = recorder.record_completed_phase(
        "upload_parse",
        duration_ms=12.5,
        started_at="2026-03-29T10:00:00",
        completed_at="2026-03-29T10:00:01",
        metadata={"uploaded_file_count": 1},
    )
    second = recorder.record_completed_phase(
        "ontology_generation",
        duration_ms=44.0,
        started_at="2026-03-29T10:00:02",
        completed_at="2026-03-29T10:00:03",
        metadata={"entity_type_count": 1, "edge_type_count": 1},
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert set(first["phases"]) == {"upload_parse"}
    assert second == payload
    assert payload["artifact_type"] == "phase_timings"
    assert payload["scope_kind"] == "project"
    assert payload["scope_id"] == "proj_test"
    assert payload["schema_version"] == "mirofish.phase_timings.v1"
    assert payload["generator_version"] == "mirofish.phase_timings.generator.v1"
    assert set(payload["phases"]) == {"upload_parse", "ontology_generation"}
    assert payload["phases"]["upload_parse"] == {
        "status": "completed",
        "duration_ms": 12.5,
        "started_at": "2026-03-29T10:00:00",
        "completed_at": "2026-03-29T10:00:01",
        "metadata": {"uploaded_file_count": 1},
    }
    assert payload["phases"]["ontology_generation"]["metadata"] == {
        "entity_type_count": 1,
        "edge_type_count": 1,
    }


def test_phase_timing_recorder_recovers_from_malformed_existing_payload(tmp_path):
    module = _load_phase_timing_module()
    artifact_path = tmp_path / "ensemble_phase_timings.json"
    artifact_path.write_text('{"artifact_type":"phase_timings","phases":{}}}', encoding="utf-8")
    recorder = module.PhaseTimingRecorder(
        artifact_path=str(artifact_path),
        scope_kind="ensemble",
        scope_id="sim_test::0001",
    )

    payload = recorder.record_completed_phase(
        "clustering",
        duration_ms=9.5,
        started_at="2026-03-31T08:00:00",
        completed_at="2026-03-31T08:00:01",
        metadata={"cluster_count": 2},
    )

    assert payload["scope_kind"] == "ensemble"
    assert payload["scope_id"] == "sim_test::0001"
    assert payload["phases"]["clustering"]["duration_ms"] == 9.5
    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert persisted["phases"]["clustering"]["metadata"] == {"cluster_count": 2}
