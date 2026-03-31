import importlib


def _load_ontology_generator_module():
    return importlib.import_module("app.services.ontology_generator")


def test_validate_and_process_normalizes_entity_names_and_source_targets():
    ontology_module = _load_ontology_generator_module()
    generator = ontology_module.OntologyGenerator(llm_client=object())

    ontology = {
        "entity_types": [
            {
                "name": "AI_Lab",
                "description": "Research lab focused on frontier AI systems.",
                "attributes": [
                    {
                        "name": "org_name",
                        "type": "text",
                        "description": "Organization name",
                    }
                ],
                "examples": ["OpenAI"],
            },
            {
                "name": "Person",
                "description": "Fallback person entity.",
                "attributes": [],
                "examples": [],
            },
            {
                "name": "Organization",
                "description": "Fallback organization entity.",
                "attributes": [],
                "examples": [],
            },
        ],
        "edge_types": [
            {
                "name": "COLLABORATES_WITH",
                "description": "Entities work together.",
                "source_targets": [
                    {"source": "AI_Lab", "target": "Person"},
                    {"source": "Person", "target": "AI_Lab"},
                ],
                "attributes": [],
            }
        ],
        "analysis_summary": "summary",
    }

    normalized = generator._validate_and_process(ontology)

    entity_names = [entity["name"] for entity in normalized["entity_types"]]

    assert "AI_Lab" not in entity_names
    assert "Organization" in entity_names
    assert normalized["edge_types"][-1]["source_targets"] == [
        {"source": "Organization", "target": "Person"},
        {"source": "Person", "target": "Organization"},
    ]


def test_validate_and_process_enforces_layered_forecast_schema_defaults():
    ontology_module = _load_ontology_generator_module()
    generator = ontology_module.OntologyGenerator(llm_client=object())

    ontology = {
        "entity_types": [
            {
                "name": "Person",
                "description": "Fallback person entity.",
                "attributes": [],
                "examples": [],
            },
            {
                "name": "Organization",
                "description": "Fallback organization entity.",
                "attributes": [],
                "examples": [],
            },
        ],
        "edge_types": [],
        "analysis_summary": "summary",
    }

    normalized = generator._validate_and_process(ontology)

    assert normalized["schema_mode"] == "forecast_layered"
    assert set(normalized["actor_types"]) == {"Person", "Organization"}
    assert set(normalized["analytical_types"]) == {
        "Event",
        "Claim",
        "Evidence",
        "Topic",
        "Metric",
        "TimeWindow",
        "Scenario",
        "UncertaintyFactor",
    }
    assert {entity["name"] for entity in normalized["entity_types"]} == {
        "Person",
        "Organization",
        "Event",
        "Claim",
        "Evidence",
        "Topic",
        "Metric",
        "TimeWindow",
        "Scenario",
        "UncertaintyFactor",
    }
    assert {
        edge["name"] for edge in normalized["edge_types"]
    } >= {
        "MAKES_CLAIM",
        "SUPPORTED_BY",
        "ABOUT_TOPIC",
        "OCCURS_DURING",
        "HAS_UNCERTAINTY",
        "INFORMS_SCENARIO",
    }
