import importlib


def test_edge_export_query_reads_optional_fields_from_properties_map():
    module = importlib.import_module("app.services.graph_backend.export_service")

    query = module._EDGE_EXPORT_QUERY

    assert "properties(r) AS edge_properties" in query
    assert "edge_properties['invalid_at'] AS invalid_at" in query
    assert "edge_properties['expired_at'] AS expired_at" in query
    assert "coalesce(edge_properties['episodes'], []) AS episodes" in query
    assert "r.invalid_at AS invalid_at" not in query
    assert "r.expired_at AS expired_at" not in query
    assert "coalesce(r.episodes, []) AS episodes" not in query
