import importlib
import sys

from pydantic import BaseModel


def _load_compiler_module():
    for module_name in (
        "app.services.graph_backend.ontology_compiler",
        "app.services.graph_backend.types",
        "app.services.graph_backend",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.ontology_compiler")


def test_ontology_compiler_builds_graphiti_models_and_edge_map():
    compiler_module = _load_compiler_module()
    compiler = compiler_module.GraphOntologyCompiler()

    compiled = compiler.compile(
        {
            "entity_types": [
                {
                    "name": "Person",
                    "description": "Forecast actor",
                    "attributes": [
                        {"name": "full_name", "type": "text", "description": "Display name"},
                        {"name": "name", "type": "text", "description": "Reserved alias"},
                    ],
                },
                {
                    "name": "Claim",
                    "description": "Forecast statement",
                    "attributes": [
                        {"name": "claim_text", "type": "text", "description": "Claim body"},
                    ],
                },
            ],
            "edge_types": [
                {
                    "name": "MAKES_CLAIM",
                    "description": "Actor states a claim",
                    "source_targets": [{"source": "person", "target": "claim"}],
                    "attributes": [
                        {
                            "name": "created_at",
                            "type": "text",
                            "description": "Reserved timestamp field",
                        },
                        {
                            "name": "confidence_label",
                            "type": "text",
                            "description": "Confidence bucket",
                        },
                    ],
                }
            ],
        }
    )

    assert issubclass(compiled.entity_types["Person"], BaseModel)
    assert issubclass(compiled.edge_types["MAKES_CLAIM"], BaseModel)
    assert "full_name" in compiled.entity_types["Person"].model_fields
    assert "entity_name" in compiled.entity_types["Person"].model_fields
    assert "edge_created_at" in compiled.edge_types["MAKES_CLAIM"].model_fields
    assert "confidence_label" in compiled.edge_types["MAKES_CLAIM"].model_fields
    assert compiled.edge_type_map[("Person", "Claim")] == ["MAKES_CLAIM"]
