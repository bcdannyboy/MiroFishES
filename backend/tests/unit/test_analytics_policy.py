import importlib


def _load_policy_module():
    return importlib.import_module("app.services.analytics_policy")


def test_analytics_policy_applies_mode_specific_eligibility_and_support_defaults():
    policy_module = _load_policy_module()
    policy = policy_module.AnalyticsPolicy()
    run_payload = {
        "run_id": "0002",
        "metrics_payload": {
            "quality_checks": {
                "status": "partial",
                "run_status": "completed",
            },
            "metric_values": {
                "simulation.total_actions": {"value": 4},
            },
        },
        "manifest_valid": True,
        "resolved_values": {"agent_configs[0].activity_level": 0.5},
    }

    aggregate = policy.assess_run(
        mode="aggregate",
        run_payload=run_payload,
        required_metric_ids=["simulation.total_actions"],
    )
    scenario = policy.assess_run(
        mode="scenario",
        run_payload=run_payload,
        required_metric_ids=["simulation.total_actions"],
    )
    sensitivity = policy.assess_run(
        mode="sensitivity",
        run_payload=run_payload,
        required_metric_ids=["simulation.total_actions"],
    )
    support = policy.build_support_metadata(support_count=1, total_count=4)

    assert aggregate["eligible"] is True
    assert "degraded_run_metrics" in aggregate["warning_hints"]
    assert scenario["eligible"] is False
    assert scenario["reasons"] == ["degraded_run_metrics"]
    assert sensitivity["eligible"] is False
    assert sensitivity["reasons"] == ["degraded_run_metrics"]
    assert support["minimum_support_count"] == 2
    assert support["minimum_support_met"] is False
    assert "minimum_support_not_met" in support["warnings"]
