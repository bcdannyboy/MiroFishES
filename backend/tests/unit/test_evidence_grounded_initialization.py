import importlib
import json
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _configure_project_grounding_dir(monkeypatch, project_root: Path):
    project_module = importlib.import_module("app.models.project")
    monkeypatch.setattr(
        project_module.ProjectManager,
        "PROJECTS_DIR",
        str(project_root),
        raising=False,
    )


def _write_grounding_artifacts(monkeypatch, tmp_path: Path, *, project_id: str) -> None:
    _configure_project_grounding_dir(monkeypatch, tmp_path / "projects")
    project_dir = tmp_path / "projects" / project_id
    _write_json(
        project_dir / "source_manifest.json",
        {
            "artifact_type": "source_manifest",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "created_at": "2026-03-31T08:00:00",
            "source_count": 1,
            "sources": [
                {
                    "source_id": "src-1",
                    "original_filename": "briefing.md",
                    "saved_filename": "briefing.md",
                    "relative_path": "files/briefing.md",
                    "size_bytes": 100,
                    "sha256": "hash-1",
                    "content_kind": "document",
                    "extraction_status": "succeeded",
                    "extracted_text_length": 100,
                    "combined_text_start": 0,
                    "combined_text_end": 100,
                    "parser_warnings": [],
                    "excerpt": "Payroll growth cooled while inflation revisions remained a risk.",
                }
            ],
        },
    )
    _write_json(
        project_dir / "source_units.json",
        {
            "artifact_type": "source_units",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "generated_at": "2026-03-31T08:01:00",
            "unit_count": 2,
            "units": [
                {
                    "unit_id": "su-1",
                    "source_id": "src-1",
                    "stable_source_id": "briefing-md",
                    "original_filename": "briefing.md",
                    "relative_path": "files/briefing.md",
                    "source_order": 1,
                    "unit_order": 1,
                    "unit_type": "paragraph",
                    "char_start": 0,
                    "char_end": 53,
                    "combined_text_start": 0,
                    "combined_text_end": 53,
                    "text": "Payroll growth cooled and the labor market softened.",
                    "metadata": {"heading_path": ["Labor"]},
                    "extraction_warnings": [],
                },
                {
                    "unit_id": "su-2",
                    "source_id": "src-1",
                    "stable_source_id": "briefing-md",
                    "original_filename": "briefing.md",
                    "relative_path": "files/briefing.md",
                    "source_order": 1,
                    "unit_order": 2,
                    "unit_type": "paragraph",
                    "char_start": 54,
                    "char_end": 100,
                    "combined_text_start": 54,
                    "combined_text_end": 100,
                    "text": "Inflation revisions could delay policy easing.",
                    "metadata": {"heading_path": ["Risks"]},
                    "extraction_warnings": [],
                },
            ],
        },
    )
    _write_json(
        project_dir / "graph_build_summary.json",
        {
            "artifact_type": "graph_build_summary",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": "graph-1",
            "generated_at": "2026-03-31T08:02:00",
            "source_artifacts": {
                "source_manifest": "source_manifest.json",
                "source_units": "source_units.json",
            },
            "ontology_summary": {
                "analysis_summary": "Labor slowdown evidence supports easing, but inflation revisions add uncertainty.",
                "entity_type_count": 4,
                "edge_type_count": 2,
            },
            "chunk_count": 2,
            "graph_counts": {
                "node_count": 4,
                "edge_count": 3,
                "entity_types": ["Organization", "Topic", "Claim", "UncertaintyFactor"],
            },
            "citation_coverage": {
                "source_unit_backed_node_count": 4,
                "source_unit_backed_edge_count": 2,
                "edge_episode_link_count": 0,
            },
            "warnings": [],
        },
    )
    _write_json(
        project_dir / "graph_entity_index.json",
        {
            "artifact_type": "graph_entity_index",
            "schema_version": "forecast.grounding.v1",
            "generator_version": "forecast.grounding.generator.v1",
            "project_id": project_id,
            "graph_id": "graph-1",
            "generated_at": "2026-03-31T08:03:00",
            "total_count": 1,
            "filtered_count": 1,
            "entity_types": ["Organization"],
            "entities": [
                {
                    "uuid": "actor-1",
                    "name": "Central Bank",
                    "labels": ["Entity", "Organization"],
                    "summary": "Monitors labor and inflation conditions.",
                    "attributes": {"role": "policy"},
                    "related_edges": [
                        {
                            "direction": "outgoing",
                            "edge_name": "tracks",
                            "fact": "Central Bank tracks payroll growth.",
                            "target_node_uuid": "topic-1",
                            "provenance": {
                                "source_unit_ids": ["su-1"],
                                "citations": [
                                    {
                                        "unit_id": "su-1",
                                        "source_id": "src-1",
                                        "stable_source_id": "briefing-md",
                                        "original_filename": "briefing.md",
                                        "relative_path": "files/briefing.md",
                                        "unit_type": "paragraph",
                                        "char_start": 0,
                                        "char_end": 53,
                                        "combined_text_start": 0,
                                        "combined_text_end": 53,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "topic-1",
                            "name": "Payroll growth",
                            "labels": ["Entity", "Topic"],
                            "summary": "Payroll growth cooled.",
                        },
                        {
                            "uuid": "claim-1",
                            "name": "Labor market softening",
                            "labels": ["Entity", "Claim"],
                            "summary": "Labor data supports easing.",
                        },
                    ],
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "briefing-md",
                                "original_filename": "briefing.md",
                                "relative_path": "files/briefing.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 53,
                                "combined_text_start": 0,
                                "combined_text_end": 53,
                            }
                        ],
                    },
                }
            ],
            "analytical_object_count": 3,
            "analytical_types": ["Claim", "Topic", "UncertaintyFactor"],
            "analytical_objects": [
                {
                    "uuid": "topic-1",
                    "name": "Payroll growth",
                    "labels": ["Entity", "Topic"],
                    "summary": "Payroll growth cooled.",
                    "object_type": "Topic",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "briefing-md",
                                "original_filename": "briefing.md",
                                "relative_path": "files/briefing.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 53,
                                "combined_text_start": 0,
                                "combined_text_end": 53,
                            }
                        ],
                    },
                    "related_edges": [],
                    "related_nodes": [
                        {
                            "uuid": "actor-1",
                            "name": "Central Bank",
                            "labels": ["Entity", "Organization"],
                            "summary": "Monitors labor and inflation conditions.",
                        }
                    ],
                },
                {
                    "uuid": "claim-1",
                    "name": "Labor market softening",
                    "labels": ["Entity", "Claim"],
                    "summary": "Labor data supports easing.",
                    "object_type": "Claim",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-1"],
                        "citations": [
                            {
                                "unit_id": "su-1",
                                "source_id": "src-1",
                                "stable_source_id": "briefing-md",
                                "original_filename": "briefing.md",
                                "relative_path": "files/briefing.md",
                                "unit_type": "paragraph",
                                "char_start": 0,
                                "char_end": 53,
                                "combined_text_start": 0,
                                "combined_text_end": 53,
                            }
                        ],
                    },
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "supports",
                            "fact": "Payroll growth cooled and the labor market softened.",
                            "source_node_uuid": "topic-1",
                            "provenance": {
                                "source_unit_ids": ["su-1"],
                                "citations": [
                                    {
                                        "unit_id": "su-1",
                                        "source_id": "src-1",
                                        "stable_source_id": "briefing-md",
                                        "original_filename": "briefing.md",
                                        "relative_path": "files/briefing.md",
                                        "unit_type": "paragraph",
                                        "char_start": 0,
                                        "char_end": 53,
                                        "combined_text_start": 0,
                                        "combined_text_end": 53,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "actor-1",
                            "name": "Central Bank",
                            "labels": ["Entity", "Organization"],
                            "summary": "Monitors labor and inflation conditions.",
                        }
                    ],
                },
                {
                    "uuid": "unc-1",
                    "name": "Inflation revision risk",
                    "labels": ["Entity", "UncertaintyFactor"],
                    "summary": "Inflation revisions could delay easing.",
                    "object_type": "UncertaintyFactor",
                    "layer": "analytical",
                    "provenance": {
                        "source_unit_ids": ["su-2"],
                        "citations": [
                            {
                                "unit_id": "su-2",
                                "source_id": "src-1",
                                "stable_source_id": "briefing-md",
                                "original_filename": "briefing.md",
                                "relative_path": "files/briefing.md",
                                "unit_type": "paragraph",
                                "char_start": 54,
                                "char_end": 100,
                                "combined_text_start": 54,
                                "combined_text_end": 100,
                            }
                        ],
                    },
                    "related_edges": [
                        {
                            "direction": "incoming",
                            "edge_name": "contradicts",
                            "fact": "Inflation revisions could delay policy easing.",
                            "source_node_uuid": "claim-1",
                            "provenance": {
                                "source_unit_ids": ["su-2"],
                                "citations": [
                                    {
                                        "unit_id": "su-2",
                                        "source_id": "src-1",
                                        "stable_source_id": "briefing-md",
                                        "original_filename": "briefing.md",
                                        "relative_path": "files/briefing.md",
                                        "unit_type": "paragraph",
                                        "char_start": 54,
                                        "char_end": 100,
                                        "combined_text_start": 54,
                                        "combined_text_end": 100,
                                    }
                                ],
                            },
                        }
                    ],
                    "related_nodes": [
                        {
                            "uuid": "actor-1",
                            "name": "Central Bank",
                            "labels": ["Entity", "Organization"],
                            "summary": "Monitors labor and inflation conditions.",
                        }
                    ],
                },
            ],
            "citation_coverage": {
                "source_unit_backed_node_count": 4,
                "source_unit_backed_edge_count": 2,
                "edge_episode_link_count": 0,
            },
        },
    )


def _build_entity():
    reader_module = importlib.import_module("app.services.zep_entity_reader")
    return reader_module.EntityNode(
        uuid="actor-1",
        name="Central Bank",
        labels=["Entity", "Organization"],
        summary="Monitors labor and inflation conditions.",
        attributes={"role": "policy"},
        related_edges=[],
        related_nodes=[],
    )


def _build_world_state():
    return {
        "artifact_type": "prepared_world_state",
        "world_summary": {
            "headline": "Labor data supports easing but inflation revisions add uncertainty."
        },
        "registries": {
            "topics": [{"uuid": "topic-1", "name": "Payroll growth"}],
            "claims": [{"uuid": "claim-1", "name": "Labor market softening"}],
            "uncertainty_factors": [{"uuid": "unc-1", "name": "Inflation revision risk"}],
            "evidence": [],
            "metrics": [],
            "time_windows": [],
            "scenarios": [],
            "events": [],
        },
        "evidence_signals": [
            {
                "signal": "supports",
                "citation_ids": ["[SUu1]"],
                "source_unit_ids": ["su-1"],
                "assumption": "Labor market softening",
            },
            {
                "signal": "mixed",
                "citation_ids": ["[GOU1]"],
                "source_unit_ids": ["su-2"],
                "counterevidence": "Inflation revision risk",
            },
        ],
    }


def _build_agent_state():
    return {
        "entity_uuid": "actor-1",
        "entity_name": "Central Bank",
        "entity_type": "Organization",
        "topic_names": ["Payroll growth"],
        "claim_names": ["Labor market softening"],
        "uncertainty_names": ["Inflation revision risk"],
        "evidence_names": [],
        "metric_names": [],
        "time_window_names": [],
        "scenario_names": [],
        "event_names": [],
        "citation_ids": ["[SUu1]", "[GOU1]"],
        "source_unit_ids": ["su-1", "su-2"],
        "evidence_signals": [
            {"signal": "supports", "assumption": "Labor market softening"},
            {"signal": "mixed", "counterevidence": "Inflation revision risk"},
        ],
        "stance_hint": "cautious",
        "sentiment_bias_hint": 0.1,
        "worldview_summary": "Evidence favors easing, but inflation revisions argue for caution.",
    }


def test_prepared_world_state_compiler_builds_world_and_agent_views(monkeypatch, tmp_path):
    module = importlib.import_module("app.services.world_state_compiler")
    forecasting_module = importlib.import_module("app.models.forecasting")

    _write_grounding_artifacts(monkeypatch, tmp_path, project_id="proj-1")

    class _FakeEvidenceBundleService:
        def build_bundle(self, *, question, existing_bundle=None, bundle_id=None, provider_ids=None):
            return forecasting_module.EvidenceBundle.from_dict(
                {
                    "bundle_id": "bundle-1",
                    "forecast_id": question.forecast_id,
                    "title": "Preparation bundle",
                    "summary": "Hybrid retrieval bundle",
                    "source_entries": [
                        {
                            "source_id": "su-1",
                            "provider_id": "uploaded_local_artifact",
                            "provider_kind": "uploaded_local_artifact",
                            "kind": "uploaded_source",
                            "title": "briefing.md",
                            "summary": "Payroll growth cooled and the labor market softened.",
                            "citation_id": "[SUu1]",
                            "locator": "files/briefing.md#chars=0-53",
                            "provenance": {
                                "project_id": "proj-1",
                                "source_unit_ids": ["su-1"],
                            },
                            "relevance": {"status": "high", "score": 0.92},
                            "quality": {"status": "strong", "score": 0.88},
                            "metadata": {
                                "forecast_hints": [
                                    {
                                        "signal": "supports",
                                        "assumption": "Labor market softening",
                                        "citation_ids": ["[SUu1]"],
                                        "source_unit_ids": ["su-1"],
                                    }
                                ]
                            },
                        },
                        {
                            "source_id": "unc-1",
                            "provider_id": "uploaded_local_artifact",
                            "provider_kind": "uploaded_local_artifact",
                            "kind": "graph_provenance",
                            "title": "Inflation revision risk",
                            "summary": "Inflation revisions could delay easing.",
                            "citation_id": "[GOU1]",
                            "locator": "graph:unc-1",
                            "provenance": {
                                "project_id": "proj-1",
                                "source_unit_ids": ["su-2"],
                            },
                            "conflict_status": "mixed",
                            "conflict_markers": [{"code": "mixed", "summary": "Inflation revision risk"}],
                            "relevance": {"status": "high", "score": 0.81},
                            "quality": {"status": "usable", "score": 0.74},
                            "metadata": {
                                "forecast_hints": [
                                    {
                                        "signal": "mixed",
                                        "counterevidence": "Inflation revision risk",
                                        "citation_ids": ["[GOU1]"],
                                        "source_unit_ids": ["su-2"],
                                    }
                                ]
                            },
                        },
                    ],
                    "provider_snapshots": [
                        {
                            "provider_id": "uploaded_local_artifact",
                            "provider_kind": "uploaded_local_artifact",
                            "status": "ready",
                            "collected_at": "2026-03-31T08:04:00",
                        }
                    ],
                    "created_at": "2026-03-31T08:04:00",
                    "boundary_note": "bounded",
                    "status": "ready",
                }
            )

    compiler = module.PreparedWorldStateCompiler(
        evidence_bundle_service=_FakeEvidenceBundleService()
    )
    compiled = compiler.compile(
        simulation_id="sim-1",
        project_id="proj-1",
        graph_id="graph-1",
        simulation_requirement="Will easing sentiment spread?",
        entities=[_build_entity()],
    )

    world_state = compiled["world_state"]
    agent_states = compiled["agent_states"]

    assert world_state["artifact_type"] == "prepared_world_state"
    assert world_state["retrieval_contract"]["status"] == "ready"
    assert [item["name"] for item in world_state["registries"]["topics"]] == ["Payroll growth"]
    assert [item["name"] for item in world_state["registries"]["claims"]] == ["Labor market softening"]
    assert [item["name"] for item in world_state["registries"]["uncertainty_factors"]] == [
        "Inflation revision risk"
    ]
    assert world_state["evidence_signals"][0]["signal"] == "supports"
    assert world_state["conflict_summary"]["mixed_count"] == 1
    assert agent_states["agent_state_count"] == 1
    assert agent_states["agent_states"][0]["topic_names"] == ["Payroll growth"]
    assert agent_states["agent_states"][0]["stance_hint"] == "cautious"
    assert agent_states["agent_states"][0]["citation_ids"] == ["[SUu1]", "[GOU1]"]


def test_oasis_profile_generator_rule_based_uses_agent_state_topics_and_signals():
    module = importlib.import_module("app.services.oasis_profile_generator")
    generator = module.OasisProfileGenerator(
        api_key="test-key",
        base_url="http://example.test/v1",
        model_name="test-model",
    )

    profile = generator.generate_profile_from_entity(
        entity=_build_entity(),
        user_id=7,
        use_llm=False,
        world_state=_build_world_state(),
        agent_state=_build_agent_state(),
    )

    assert "Payroll growth" in profile.bio
    assert "Labor market softening" in profile.persona
    assert "Inflation revision risk" in profile.persona
    assert profile.interested_topics[:2] == ["Payroll growth", "Labor market softening"]


def test_simulation_config_generator_applies_world_state_defaults_after_sparse_llm_output(monkeypatch):
    module = importlib.import_module("app.services.simulation_config_generator")
    generator = module.SimulationConfigGenerator(
        api_key="test-key",
        base_url="http://example.test/v1",
        model_name="test-model",
    )

    monkeypatch.setattr(generator, "_generate_time_config", lambda context, num_entities: {})
    monkeypatch.setattr(
        generator,
        "_generate_event_config",
        lambda context, simulation_requirement, entities: {
            "hot_topics": [],
            "narrative_direction": "",
            "initial_posts": [],
            "reasoning": "sparse",
        },
    )
    monkeypatch.setattr(
        generator,
        "_generate_agent_configs_batch",
        lambda **kwargs: [
            module.AgentActivityConfig(
                agent_id=0,
                entity_uuid="actor-1",
                entity_name="Central Bank",
                entity_type="Organization",
                stance="neutral",
                sentiment_bias=0.0,
            )
        ],
    )

    params = generator.generate_config(
        simulation_id="sim-1",
        project_id="proj-1",
        graph_id="graph-1",
        simulation_requirement="Will easing sentiment spread?",
        document_text="seed text",
        entities=[_build_entity()],
        enable_twitter=True,
        enable_reddit=True,
        world_state=_build_world_state(),
        agent_states_by_uuid={"actor-1": _build_agent_state()},
    )

    assert params.event_config.hot_topics == ["Payroll growth"]
    assert "inflation revisions" in params.event_config.narrative_direction.lower()
    assert params.agent_configs[0].stance == "cautious"
    assert params.agent_configs[0].sentiment_bias == 0.1
