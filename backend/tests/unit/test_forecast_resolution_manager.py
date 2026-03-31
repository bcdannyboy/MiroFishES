from __future__ import annotations

import importlib


def _load_forecasting_module():
    return importlib.import_module("app.models.forecasting")


def _load_manager_module():
    return importlib.import_module("app.services.forecast_manager")


def _load_resolution_manager_module():
    return importlib.import_module("app.services.forecast_resolution_manager")


def test_forecast_resolution_manager_scores_binary_latest_answer(
    forecast_data_dir,
    monkeypatch,
):
    forecasting_module = _load_forecasting_module()
    manager_module = _load_manager_module()
    monkeypatch.setattr(
        manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    manager = manager_module.ForecastManager(forecast_data_dir=str(forecast_data_dir))
    workspace = manager.create_question(
        forecasting_module.ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-binary-score",
                "project_id": "proj-1",
                "title": "Binary score",
                "question": "Will support exceed 55%?",
                "question_type": "binary",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
                "primary_simulation_id": "sim-001",
            }
        )
    )
    workspace.forecast_answers.append(
        forecasting_module.ForecastAnswer.from_dict(
            {
                "answer_id": "answer-binary-1",
                "forecast_id": "forecast-binary-score",
                "answer_type": "hybrid_forecast",
                "summary": "Binary answer.",
                "worker_ids": ["worker-base"],
                "prediction_entry_ids": [],
                "confidence_semantics": "uncalibrated",
                "created_at": "2026-03-30T10:00:00",
                "answer_payload": {
                    "best_estimate": {
                        "value": 0.67,
                        "value_semantics": "forecast_probability",
                    }
                },
            }
        )
    )
    manager.save_workspace(workspace)
    manager.resolve_forecast(
        "forecast-binary-score",
        {
            "status": "resolved_true",
            "resolved_at": "2026-07-01T10:00:00",
            "resolution_note": "Observed yes.",
        },
    )

    resolution_manager_module = _load_resolution_manager_module()
    resolution_manager = resolution_manager_module.ForecastResolutionManager(
        forecast_data_dir=str(forecast_data_dir)
    )
    scored_workspace = resolution_manager.score_forecast(
        "forecast-binary-score",
        observed_outcome=True,
        scoring_methods=["brier_score", "log_score"],
        recorded_at="2026-07-01T10:05:00",
    )

    assert [event.scoring_method for event in scored_workspace.scoring_events] == [
        "brier_score",
        "log_score",
    ]
    assert scored_workspace.scoring_events[0].score_value == 0.1089
    assert scored_workspace.scoring_events[0].status == "scored"
    assert scored_workspace.lifecycle_metadata.current_stage == "scoring_event"


def test_forecast_resolution_manager_scores_categorical_latest_answer(
    forecast_data_dir,
    monkeypatch,
):
    forecasting_module = _load_forecasting_module()
    manager_module = _load_manager_module()
    monkeypatch.setattr(
        manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    manager = manager_module.ForecastManager(forecast_data_dir=str(forecast_data_dir))
    workspace = manager.create_question(
        forecasting_module.ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-categorical-score",
                "project_id": "proj-1",
                "title": "Categorical score",
                "question": "Which launch posture will be observed?",
                "question_type": "categorical",
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
                "primary_simulation_id": "sim-001",
                "question_spec": {
                    "outcome_labels": ["win", "stretch", "miss"],
                },
            }
        )
    )
    workspace.forecast_answers.append(
        forecasting_module.ForecastAnswer.from_dict(
            {
                "answer_id": "answer-categorical-1",
                "forecast_id": "forecast-categorical-score",
                "answer_type": "hybrid_forecast",
                "summary": "Categorical answer.",
                "worker_ids": ["worker-base"],
                "prediction_entry_ids": [],
                "confidence_semantics": "uncalibrated",
                "created_at": "2026-03-30T10:00:00",
                "answer_payload": {
                    "best_estimate": {
                        "value_type": "categorical_distribution",
                        "value_semantics": "forecast_distribution",
                        "top_label": "win",
                        "top_label_share": 0.62,
                        "distribution": {
                            "win": 0.62,
                            "stretch": 0.24,
                            "miss": 0.14,
                        },
                    }
                },
            }
        )
    )
    manager.save_workspace(workspace)
    manager.resolve_forecast(
        "forecast-categorical-score",
        {
            "status": "resolved",
            "resolved_at": "2026-07-01T10:00:00",
            "resolution_note": "Observed win.",
        },
    )

    resolution_manager_module = _load_resolution_manager_module()
    resolution_manager = resolution_manager_module.ForecastResolutionManager(
        forecast_data_dir=str(forecast_data_dir)
    )
    scored_workspace = resolution_manager.score_forecast(
        "forecast-categorical-score",
        observed_outcome="win",
        scoring_methods=[
            "multiclass_log_loss",
            "multiclass_brier_score",
            "top1_accuracy",
        ],
        recorded_at="2026-07-01T10:05:00",
    )

    assert [event.scoring_method for event in scored_workspace.scoring_events] == [
        "multiclass_log_loss",
        "multiclass_brier_score",
        "top1_accuracy",
    ]
    assert scored_workspace.scoring_events[2].score_value == 1.0
    assert scored_workspace.scoring_events[2].status == "scored"


def test_forecast_resolution_manager_scores_numeric_latest_answer(
    forecast_data_dir,
    monkeypatch,
):
    forecasting_module = _load_forecasting_module()
    manager_module = _load_manager_module()
    monkeypatch.setattr(
        manager_module.ForecastManager,
        "FORECAST_DATA_DIR",
        str(forecast_data_dir),
    )

    manager = manager_module.ForecastManager(forecast_data_dir=str(forecast_data_dir))
    workspace = manager.create_question(
        forecasting_module.ForecastQuestion.from_dict(
            {
                "forecast_id": "forecast-numeric-score",
                "project_id": "proj-1",
                "title": "Numeric score",
                "question": "What support level will be observed?",
                "question_type": "numeric",
                "question_spec": {
                    "unit": "share",
                    "interval_levels": [50, 80, 90],
                },
                "status": "active",
                "horizon": {"type": "date", "value": "2026-06-30"},
                "issue_timestamp": "2026-03-30T09:00:00",
                "created_at": "2026-03-30T09:00:00",
                "updated_at": "2026-03-30T09:00:00",
                "primary_simulation_id": "sim-001",
            }
        )
    )
    workspace.forecast_answers.append(
        forecasting_module.ForecastAnswer.from_dict(
            {
                "answer_id": "answer-numeric-1",
                "forecast_id": "forecast-numeric-score",
                "answer_type": "hybrid_forecast",
                "summary": "Numeric answer.",
                "worker_ids": ["worker-base"],
                "prediction_entry_ids": [],
                "confidence_semantics": "uncalibrated",
                "created_at": "2026-03-30T10:00:00",
                "answer_payload": {
                    "best_estimate": {
                        "value": 42.0,
                        "value_semantics": "numeric_point_estimate",
                    }
                },
            }
        )
    )
    manager.save_workspace(workspace)
    manager.resolve_forecast(
        "forecast-numeric-score",
        {
            "status": "resolved",
            "resolved_at": "2026-07-01T10:00:00",
            "resolution_note": "Observed 45.",
        },
    )

    resolution_manager_module = _load_resolution_manager_module()
    resolution_manager = resolution_manager_module.ForecastResolutionManager(
        forecast_data_dir=str(forecast_data_dir)
    )
    scored_workspace = resolution_manager.score_forecast(
        "forecast-numeric-score",
        observed_outcome=45,
        scoring_methods=["absolute_error", "squared_error"],
        recorded_at="2026-07-01T10:05:00",
    )

    assert [event.scoring_method for event in scored_workspace.scoring_events] == [
        "absolute_error",
        "squared_error",
    ]
    assert scored_workspace.scoring_events[0].score_value == 3.0
    assert scored_workspace.scoring_events[1].score_value == 9.0
    assert scored_workspace.scoring_events[0].status == "scored"
