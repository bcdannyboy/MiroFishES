import importlib


def test_oasis_profile_generator_exposes_only_graph_named_search_helpers():
    module = importlib.import_module("app.services.oasis_profile_generator")

    assert hasattr(module.OasisProfileGenerator, "_search_graph_for_entity")
    assert not hasattr(module.OasisProfileGenerator, "_search_zep_for_entity")
