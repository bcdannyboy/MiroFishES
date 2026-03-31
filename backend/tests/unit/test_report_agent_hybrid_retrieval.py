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
