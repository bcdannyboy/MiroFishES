import importlib
import sys


def _load_namespace_module():
    for module_name in (
        "app.services.graph_backend.namespace_manager",
        "app.services.graph_backend.types",
        "app.services.graph_backend",
    ):
        sys.modules.pop(module_name, None)
    return importlib.import_module("app.services.graph_backend.namespace_manager")


def test_namespace_manager_builds_deterministic_base_and_runtime_ids():
    namespace_module = _load_namespace_module()
    manager = namespace_module.GraphNamespaceManager(namespace_prefix="mirofish")

    base = manager.build_base_namespace(
        project_id="proj_Fed_01",
        project_name="Fed Watch",
    )
    runtime = manager.build_runtime_namespace(
        simulation_id="sim-01",
        ensemble_id="0001",
        run_id="run_0002",
    )

    assert base.namespace_id == "mirofish-base-proj-fed-01"
    assert base.group_id == "mirofish-base-proj-fed-01"
    assert base.graph_scope == "base"
    assert base.display_name == "Fed Watch base graph"

    assert runtime.namespace_id == "mirofish-runtime-sim-01-0001-run-0002"
    assert runtime.group_id == "mirofish-runtime-sim-01-0001-run-0002"
    assert runtime.graph_scope == "runtime"
    assert runtime.display_name == "Runtime graph sim-01/0001/run_0002"
