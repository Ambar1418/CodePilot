"""Metrics collector for application observability.

Tracks operational metrics: latencies, execution counts, success/failure ratios.
"""
from __future__ import annotations
import time
from typing import Dict, Any, List
from collections import defaultdict


class MetricsCollector:
    def __init__(self):
        self._counters: Dict[str, int] = defaultdict(int)
        self._latencies: Dict[str, List[float]] = defaultdict(list)

    def increment(self, metric_name: str, count: int = 1) -> None:
        self._counters[metric_name] += count

    def record_latency(self, metric_name: str, duration_seconds: float) -> None:
        self._latencies[metric_name].append(duration_seconds)
        # Keep last 1000 data points to avoid unbounded growth
        if len(self._latencies[metric_name]) > 1000:
            self._latencies[metric_name] = self._latencies[metric_name][-1000:]

    def get_metrics(self) -> Dict[str, Any]:
        latency_summary = {}
        for k, v in self._latencies.items():
            if v:
                latency_summary[k] = {
                    "count": len(v),
                    "avg_seconds": round(sum(v) / len(v), 3),
                    "min_seconds": round(min(v), 3),
                    "max_seconds": round(max(v), 3),
                }
        return {
            "counters": dict(self._counters),
            "latencies": latency_summary,
        }

    def reset(self) -> None:
        self._counters.clear()
        self._latencies.clear()


# Global metrics instance
metrics = MetricsCollector()
