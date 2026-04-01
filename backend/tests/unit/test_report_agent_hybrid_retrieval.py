from __future__ import annotations

import importlib


def test_report_agent_hybrid_evidence_tool_uses_workspace_project_context():
    module = importlib.import_module("app.services.report_agent")

    class _FakeHybridResult:
        def __init__(self, query: str):
            self.query = query

        def to_text(self) -> str:
            return "Hybrid evidence:\n- [SU1] Payroll preview supports a June rate cut."

    class _FakeZepTools:
        def __init__(self):
            self.calls = []

        def hybrid_evidence_search(self, *, project_id: str, query: str, graph_id: str, graph_ids):
            self.calls.append(
                {
                    "project_id": project_id,
                    "query": query,
                    "graph_id": graph_id,
                    "graph_ids": graph_ids,
                }
            )
            return _FakeHybridResult(query)

    zep_tools = _FakeZepTools()
    agent = module.ReportAgent(
        graph_id="graph-base",
        simulation_id="sim-1",
        simulation_requirement="Forecast policy easing momentum.",
        zep_tools=zep_tools,
        probabilistic_context={
            "forecast_workspace": {
                "forecast_question": {
                    "project_id": "proj-hybrid",
                }
            }
        },
    )

    tool_result = agent._execute_tool(
        "hybrid_evidence_search",
        {"query": "What supports a June rate cut?"},
    )

    assert "Hybrid evidence:" in tool_result
    assert zep_tools.calls == [
        {
            "project_id": "proj-hybrid",
            "query": "What supports a June rate cut?",
            "graph_id": "graph-base",
            "graph_ids": ["graph-base"],
        }
    ]


def test_report_agent_quick_search_works_without_zep_credentials(
    tmp_path, monkeypatch
):
    module = importlib.import_module("app.services.report_agent")
    config_module = importlib.import_module("app.config")
    project_module = importlib.import_module("app.models.project")
    json_module = importlib.import_module("json")

    monkeypatch.setattr(config_module.Config, "ZEP_API_KEY", "", raising=False)
    monkeypatch.setattr(
        config_module.Config,
        "OASIS_SIMULATION_DATA_DIR",
        str(tmp_path / "simulations"),
        raising=False,
    )
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(tmp_path / "projects"),
        raising=False,
    )

    project_dir = tmp_path / "projects" / "proj-report"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        json_module.dumps(
            {
                "project_id": "proj-report",
                "name": "Report Graph Project",
                "status": "graph_completed",
                "created_at": "2026-03-31T08:00:00",
                "updated_at": "2026-03-31T08:00:00",
                "files": [],
                "graph_id": "graph-base",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (project_dir / "graph_entity_index.json").write_text(
        json_module.dumps(
            {
                "artifact_type": "graph_entity_index",
                "project_id": "proj-report",
                "graph_id": "graph-base",
                "total_count": 1,
                "filtered_count": 1,
                "entity_types": ["Person"],
                "entities": [
                    {
                        "uuid": "actor-1",
                        "name": "Analyst",
                        "labels": ["Entity", "Person"],
                        "summary": "Tracks labor-market conditions.",
                        "attributes": {"role": "analyst"},
                        "related_edges": [
                            {
                                "direction": "outgoing",
                                "edge_name": "MENTIONS",
                                "fact": "Analyst says hiring is slowing.",
                                "target_node_uuid": "topic-1",
                            }
                        ],
                        "related_nodes": [
                            {
                                "uuid": "topic-1",
                                "name": "Labor slowdown",
                                "labels": ["Entity", "Topic"],
                                "summary": "Employment is cooling.",
                            }
                        ],
                    }
                ],
                "analytical_object_count": 1,
                "analytical_types": ["Topic"],
                "analytical_objects": [
                    {
                        "uuid": "topic-1",
                        "name": "Labor slowdown",
                        "object_type": "Topic",
                        "summary": "Employment is cooling.",
                        "related_edges": [
                            {
                                "direction": "incoming",
                                "edge_name": "MENTIONS",
                                "fact": "Analyst says hiring is slowing.",
                                "source_node_uuid": "actor-1",
                            }
                        ],
                        "related_nodes": [
                            {
                                "uuid": "actor-1",
                                "name": "Analyst",
                                "labels": ["Entity", "Person"],
                                "summary": "Tracks labor-market conditions.",
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    run_dir = (
        tmp_path
        / "simulations"
        / "sim-report"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        json_module.dumps(
            {
                "simulation_id": "sim-report",
                "ensemble_id": "0001",
                "run_id": "0001",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "runtime_graph_base_snapshot.json").write_text(
        json_module.dumps(
            {
                "artifact_type": "runtime_graph_base_snapshot",
                "simulation_id": "sim-report",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-report",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
                "actors": [
                    {
                        "entity_uuid": "actor-1",
                        "entity_name": "Analyst",
                        "entity_type": "Person",
                        "summary": "Tracks labor-market conditions.",
                        "linked_object_uuids": ["topic-1"],
                    }
                ],
                "analytical_objects": [
                    {
                        "uuid": "topic-1",
                        "name": "Labor slowdown",
                        "object_type": "Topic",
                        "summary": "Employment is cooling.",
                    }
                ],
                "registries": {
                    "topics": [
                        {
                            "uuid": "topic-1",
                            "name": "Labor slowdown",
                            "citation_ids": ["cit-1"],
                            "source_unit_ids": ["unit-1"],
                            "linked_actor_uuids": ["actor-1"],
                        }
                    ]
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "runtime_graph_state.json").write_text(
        json_module.dumps(
            {
                "artifact_type": "runtime_graph_state",
                "simulation_id": "sim-report",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-report",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
                "transition_count": 1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "runtime_graph_updates.jsonl").write_text(
        json_module.dumps(
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-claim",
                "transition_type": "claim",
                "simulation_id": "sim-report",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-report",
                "base_graph_id": "graph-base",
                "runtime_graph_id": "runtime-graph-1",
                "platform": "twitter",
                "round_num": 1,
                "timestamp": "2026-03-31T09:00:00",
                "recorded_at": "2026-03-31T09:00:05",
                "agent": {
                    "agent_name": "Analyst",
                    "entity_uuid": "actor-1",
                    "entity_type": "Person",
                },
                "payload": {
                    "action_type": "CREATE_POST",
                    "topics": ["Labor slowdown"],
                    "action_args": {
                        "content": "Hiring is weakening.",
                        "topic": "Labor slowdown",
                    },
                },
                "provenance": {
                    "run_scope": "sim-report::0001::0001",
                    "citation_ids": ["cit-1"],
                    "source_unit_ids": ["unit-1"],
                    "graph_object_uuids": ["topic-1"],
                },
                "source_artifact": "twitter/actions.jsonl",
                "human_readable": "Analyst create_post :: Hiring is weakening.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    agent = module.ReportAgent(
        graph_id="graph-base",
        base_graph_id="graph-base",
        runtime_graph_id="runtime-graph-1",
        graph_ids=["graph-base", "runtime-graph-1"],
        simulation_id="sim-report",
        simulation_requirement="Forecast labor-market momentum.",
        llm_client=object(),
    )

    tool_result = agent._execute_tool(
        "quick_search",
        {"query": "hiring", "limit": 5},
    )

    assert "Analyst says hiring is slowing." in tool_result
    assert "Hiring is weakening." in tool_result


def test_report_agent_defaults_to_graph_query_tools_service(monkeypatch):
    module = importlib.import_module("app.services.report_agent")

    class _FakeGraphTools:
        pass

    monkeypatch.setattr(
        module,
        "GraphQueryToolsService",
        lambda: _FakeGraphTools(),
        raising=False,
    )

    agent = module.ReportAgent(
        graph_id="graph-base",
        simulation_id="sim-graph-tools",
        simulation_requirement="Track runtime graph changes.",
    )

    assert isinstance(agent.zep_tools, _FakeGraphTools)
