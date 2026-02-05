from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class OperationalEvent:
    endpoint: str
    latency_ms: float
    request_id: str
    user_plan: str = "unknown"
    error: Optional[str] = None
    status_code: int = 200
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def hour(self) -> int:
        return self.ts.hour


class StructuredOperationalLogger:
    """Padroniza os campos operacionais para logs estruturados e analytics."""

    REQUIRED_KEYS = ("latency_ms", "error", "endpoint", "user_plan", "request_id")

    def build_payload(self, event: OperationalEvent) -> Dict[str, Any]:
        payload = {
            "latency_ms": round(event.latency_ms, 2),
            "error": event.error,
            "endpoint": event.endpoint,
            "user_plan": event.user_plan,
            "request_id": event.request_id,
            "status_code": event.status_code,
            "ts": event.ts.isoformat(),
        }
        return payload


class TimeSeriesIngestionPipeline:
    """Pipeline de ingestão em memória para séries temporais e logs analíticos."""

    def __init__(self) -> None:
        self.metrics: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []

    def ingest(self, payload: Dict[str, Any]) -> None:
        metric = {
            "ts": payload["ts"],
            "endpoint": payload["endpoint"],
            "latency_ms": payload["latency_ms"],
            "status_code": payload["status_code"],
            "hour": datetime.fromisoformat(payload["ts"]).hour,
        }
        self.metrics.append(metric)
        self.logs.append(payload)


class BaselineAnomalyDetector:
    """Baseline estatístico por endpoint e hora (ML leve sem dependências externas)."""

    def __init__(self) -> None:
        self.model: Dict[Tuple[str, int], Dict[str, float]] = {}

    def train(self, metrics: List[Dict[str, Any]]) -> Dict[Tuple[str, int], Dict[str, float]]:
        grouped: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}
        for row in metrics:
            key = (row["endpoint"], int(row["hour"]))
            grouped.setdefault(key, []).append(row)

        for key, rows in grouped.items():
            latencies = [float(r["latency_ms"]) for r in rows]
            errors = [1.0 if int(r["status_code"]) >= 500 else 0.0 for r in rows]
            baseline_std = pstdev(latencies) if len(latencies) > 1 else 1.0
            self.model[key] = {
                "latency_mean": mean(latencies),
                "latency_std": baseline_std or 1.0,
                "error_rate": mean(errors),
                "samples": float(len(rows)),
            }
        return self.model

    def score(self, metric: Dict[str, Any]) -> Dict[str, float]:
        key = (metric["endpoint"], int(metric["hour"]))
        baseline = self.model.get(key)
        if not baseline:
            return {"z_score": 0.0, "error_delta": 0.0, "anomaly_score": 0.0}

        z_score = abs((float(metric["latency_ms"]) - baseline["latency_mean"]) / max(baseline["latency_std"], 1.0))
        current_error = 1.0 if int(metric["status_code"]) >= 500 else 0.0
        error_delta = max(0.0, current_error - baseline["error_rate"])
        anomaly_score = (0.7 * z_score) + (0.3 * error_delta * 10)
        return {"z_score": z_score, "error_delta": error_delta, "anomaly_score": anomaly_score}


class RealtimeAlertEngine:
    """Gera alertas em tempo real com severidade e causa provável."""

    def classify(self, payload: Dict[str, Any], scores: Dict[str, float]) -> Optional[Dict[str, Any]]:
        score = scores["anomaly_score"]
        if score < 2.5:
            return None

        if score >= 7:
            severity = "critical"
        elif score >= 4:
            severity = "high"
        else:
            severity = "medium"

        probable_cause = "spike de latência"
        if payload.get("status_code", 200) >= 500:
            probable_cause = "aumento de erros 5xx"
        elif scores["z_score"] > 5:
            probable_cause = "degradação de dependência externa"

        return {
            "endpoint": payload["endpoint"],
            "request_id": payload["request_id"],
            "severity": severity,
            "probable_cause": probable_cause,
            "anomaly_score": round(score, 2),
            "ts": payload["ts"],
        }


class RootCauseAnalyzer:
    """Correlaciona deploys, erros e latência para causa raiz orientada a logs."""

    def analyze(self, alert: Dict[str, Any], logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        endpoint_logs = [l for l in logs if l.get("endpoint") == alert["endpoint"]]
        recent = endpoint_logs[-30:]
        deploy_hit = any(l.get("event_type") == "deploy" for l in recent)
        error_ratio = 0.0
        if recent:
            error_ratio = sum(1 for l in recent if int(l.get("status_code", 200)) >= 500) / len(recent)

        root = "instabilidade operacional"
        if deploy_hit and error_ratio > 0.2:
            root = "possível regressão pós-deploy"
        elif error_ratio > 0.4:
            root = "falha sistêmica da aplicação"
        elif alert["probable_cause"] == "degradação de dependência externa":
            root = "dependência externa lenta"

        return {
            "root_cause": root,
            "error_ratio": round(error_ratio, 3),
            "deploy_correlation": deploy_hit,
        }


class FeedbackLoop:
    """Retroalimenta alertas confirmados para reduzir falso positivo."""

    def __init__(self) -> None:
        self.confirmed_alerts: List[Dict[str, Any]] = []
        self.rejected_alerts: List[Dict[str, Any]] = []

    def register_feedback(self, alert: Dict[str, Any], confirmed: bool) -> None:
        (self.confirmed_alerts if confirmed else self.rejected_alerts).append(alert)

    def false_positive_rate(self) -> float:
        total = len(self.confirmed_alerts) + len(self.rejected_alerts)
        if total == 0:
            return 0.0
        return len(self.rejected_alerts) / total


class ModelRegistry:
    """Versiona modelos e acompanha avaliação contínua com impacto em MTTR."""

    def __init__(self) -> None:
        self.versions: List[Dict[str, Any]] = []

    def register(self, version: str, metrics: Dict[str, float]) -> Dict[str, Any]:
        record = {
            "version": version,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "precision": metrics.get("precision", 0.0),
            "recall": metrics.get("recall", 0.0),
            "mttr_impact_minutes": metrics.get("mttr_impact_minutes", 0.0),
        }
        self.versions.append(record)
        return record


class ObservabilityOrchestrator:
    def __init__(self) -> None:
        self.logger = StructuredOperationalLogger()
        self.ingestion = TimeSeriesIngestionPipeline()
        self.detector = BaselineAnomalyDetector()
        self.alerts = RealtimeAlertEngine()
        self.rca = RootCauseAnalyzer()
        self.feedback = FeedbackLoop()
        self.registry = ModelRegistry()

    def process_event(self, event: OperationalEvent) -> Dict[str, Any]:
        payload = self.logger.build_payload(event)
        self.ingestion.ingest(payload)

        metric = self.ingestion.metrics[-1]
        scores = self.detector.score(metric)
        alert = self.alerts.classify(payload, scores)
        if not alert:
            return {"payload": payload, "alert": None}

        alert["root_cause"] = self.rca.analyze(alert, self.ingestion.logs)
        return {"payload": payload, "alert": alert}


observability_orchestrator = ObservabilityOrchestrator()
