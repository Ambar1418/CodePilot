import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.observability.metrics import metrics

client = TestClient(app)

def test_metrics_collector():
    metrics.reset()
    metrics.increment("test_counter", 5)
    metrics.record_latency("test_latency", 0.123)

    data = metrics.get_metrics()
    assert data["counters"]["test_counter"] == 5
    assert "test_latency" in data["latencies"]
    assert data["latencies"]["test_latency"]["count"] == 1
    assert data["latencies"]["test_latency"]["avg_seconds"] == 0.123

def test_metrics_endpoint():
    metrics.reset()
    metrics.increment("requests_total", 1)
    response = client.get("/api/metrics")
    assert response.status_code == 200
    json_data = response.json()
    assert "counters" in json_data
    assert json_data["counters"]["requests_total"] == 1
