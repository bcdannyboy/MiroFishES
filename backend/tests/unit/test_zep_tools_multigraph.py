import importlib


def test_search_graph_merges_multiple_graphs_with_deterministic_dedupe(monkeypatch):
    module = importlib.import_module("app.services.zep_tools")
    service = module.ZepToolsService.__new__(module.ZepToolsService)

    results_by_graph = {
        "graph-base": module.SearchResult(
            facts=["shared fact", "base-only fact"],
            edges=[
                {
                    "uuid": "edge-base",
                    "name": "MENTIONS",
                    "fact": "shared fact",
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                }
            ],
            nodes=[
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Base analyst summary",
                }
            ],
            query="plaza",
            total_count=2,
        ),
        "graph-runtime": module.SearchResult(
            facts=["shared fact", "runtime-only fact"],
            edges=[
                {
                    "uuid": "edge-runtime",
                    "name": "OBSERVES",
                    "fact": "runtime-only fact",
                    "source_node_uuid": "node-3",
                    "target_node_uuid": "node-4",
                }
            ],
            nodes=[
                {
                    "uuid": "node-1",
                    "name": "Analyst",
                    "labels": ["Entity", "Person"],
                    "summary": "Base analyst summary",
                },
                {
                    "uuid": "node-3",
                    "name": "Plaza",
                    "labels": ["Entity", "Place"],
                    "summary": "Runtime plaza summary",
                },
            ],
            query="plaza",
            total_count=2,
        ),
    }

    monkeypatch.setattr(
        service,
        "_search_single_graph",
        lambda graph_id, query, limit, scope: results_by_graph[graph_id],
        raising=False,
    )

    result = service.search_graph(
        graph_id="graph-base",
        graph_ids=["graph-base", "graph-runtime"],
        query="plaza",
        limit=10,
        scope="edges",
    )

    assert result.query == "plaza"
    assert result.facts == ["shared fact", "base-only fact", "runtime-only fact"]
    assert [edge["uuid"] for edge in result.edges] == ["edge-base", "edge-runtime"]
    assert [node["uuid"] for node in result.nodes] == ["node-1", "node-3"]
    assert result.total_count == 3


def test_hybrid_evidence_search_wraps_retriever_results_with_citations(monkeypatch):
    module = importlib.import_module("app.services.zep_tools")
    service = module.ZepToolsService.__new__(module.ZepToolsService)

    class _FakeRetriever:
        def retrieve(self, *, project_id, query, question_type="binary", issue_timestamp=None, limit=6):
            return type(
                "HybridResult",
                (),
                {
                    "query": query,
                    "project_id": project_id,
                    "hits": [
                        {
                            "record_id": "claim-1",
                            "record_type": "graph_object",
                            "title": "June cut likely",
                            "summary": "A June cut is supported by payroll data.",
                            "object_type": "Claim",
                            "conflict_status": "supports",
                            "forecast_hints": [{"estimate": 0.66, "confidence_weight": 0.8}],
                            "citations": [
                                {
                                    "citation_id": "[SU1]",
                                    "locator": "files/memo.md#chars=0-80",
                                }
                            ],
                            "score": 0.91,
                        }
                    ],
                    "missing_evidence_markers": [],
                    "index_stats": {"record_count": 2},
                },
            )()

    service.hybrid_evidence_retriever = _FakeRetriever()

    result = service.hybrid_evidence_search(
        project_id="proj-hybrid",
        graph_id="graph-1",
        query="What supports a June rate cut?",
    )

    assert result.query == "What supports a June rate cut?"
    assert result.total_count == 1
    assert result.entries[0]["citations"][0]["citation_id"] == "[SU1]"
    assert "[SU1]" in result.to_text()


def test_search_graph_reads_artifact_backed_multigraph_without_zep_credentials(
    monkeypatch, tmp_path
):
    module = importlib.import_module("app.services.zep_tools")
    config_module = importlib.import_module("app.config")
    project_module = importlib.import_module("app.models.project")

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

    project_dir = tmp_path / "projects" / "proj-tools"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        importlib.import_module("json").dumps(
            {
                "project_id": "proj-tools",
                "name": "Tools Project",
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
        importlib.import_module("json").dumps(
            {
                "artifact_type": "graph_entity_index",
                "project_id": "proj-tools",
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
        / "sim-tools"
        / "ensemble"
        / "ensemble_0001"
        / "runs"
        / "run_0001"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_manifest.json").write_text(
        importlib.import_module("json").dumps(
            {
                "simulation_id": "sim-tools",
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
        importlib.import_module("json").dumps(
            {
                "artifact_type": "runtime_graph_base_snapshot",
                "simulation_id": "sim-tools",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-tools",
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
        importlib.import_module("json").dumps(
            {
                "artifact_type": "runtime_graph_state",
                "simulation_id": "sim-tools",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-tools",
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
        importlib.import_module("json").dumps(
            {
                "artifact_type": "runtime_state_transition",
                "transition_id": "rts-fixed-claim",
                "transition_type": "claim",
                "simulation_id": "sim-tools",
                "ensemble_id": "0001",
                "run_id": "0001",
                "project_id": "proj-tools",
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
                    "run_scope": "sim-tools::0001::0001",
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

    service = module.ZepToolsService()
    result = service.search_graph(
        graph_id="graph-base",
        graph_ids=["graph-base", "runtime-graph-1"],
        query="hiring",
        limit=10,
        scope="edges",
    )

    assert result.facts == [
        "Analyst says hiring is slowing.",
        "Analyst create_post :: Hiring is weakening.",
    ]
    assert result.edges[0]["uuid"].startswith("graph-edge-")
    assert result.edges[1]["uuid"] == "rts-fixed-claim"
