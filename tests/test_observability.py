from datetime import datetime, timezone

from services.observability import (
    BaselineAnomalyDetector,
    FeedbackLoop,
    ModelRegistry,
    OperationalEvent,
    ObservabilityOrchestrator,
)


def test_baseline_detector_and_alert_pipeline():
    orchestrator = ObservabilityOrchestrator(training_min_samples=5)

    base_ts = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
    for latency in [90, 95, 100, 105, 110]:
        event = OperationalEvent(
            endpoint="/v1/chart/natal",
            latency_ms=latency,
            request_id=f"req-{latency}",
            user_plan="pro",
            status_code=200,
            ts=base_ts,
        )
        orchestrator.process_event(event)

    assert orchestrator.registry.versions

    anomaly = OperationalEvent(
        endpoint="/v1/chart/natal",
        latency_ms=900,
        request_id="req-anomaly",
        user_plan="pro",
        status_code=503,
        error="timeout upstream",
        ts=base_ts,
    )
    result = orchestrator.process_event(anomaly)

    assert result["alert"] is not None
    assert result["alert"]["severity"] in {"medium", "high", "critical"}
    assert "root_cause" in result["alert"]


def test_feedback_loop_and_model_registry():
    feedback = FeedbackLoop()
    alert = {"id": "a-1", "severity": "high"}

    feedback.register_feedback(alert, confirmed=True)
    feedback.register_feedback(alert, confirmed=False)

    assert feedback.false_positive_rate() == 0.5

    registry = ModelRegistry()
    record = registry.register(
        "v0.1.0",
        {"precision": 0.81, "recall": 0.72, "mttr_impact_minutes": 11.5},
    )

    assert record["version"] == "v0.1.0"
    assert record["precision"] == 0.81
    assert record["recall"] == 0.72


def test_detector_score_without_baseline():
    detector = BaselineAnomalyDetector()
    score = detector.score(
        {
            "endpoint": "/v1/none",
            "hour": 9,
            "latency_ms": 12,
            "status_code": 200,
        }
    )
    assert score["anomaly_score"] == 0.0
