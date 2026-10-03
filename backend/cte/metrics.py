"""Minimal Prometheus-compatible runtime metrics registry."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass
class MetricsRegistry:
    requests_total: Counter
    responses_total: Counter
    durations_ms_total: float = 0.0

    @classmethod
    def create(cls) -> "MetricsRegistry":
        return cls(Counter(), Counter())

    def observe_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        key = (method, path)
        self.requests_total[key] += 1
        self.responses_total[(status,)] += 1
        self.durations_ms_total += duration_ms

    def render(self) -> str:
        lines = [
            "# HELP cte_http_requests_total Total HTTP requests.",
            "# TYPE cte_http_requests_total counter",
        ]
        for (method, path), value in sorted(self.requests_total.items()):
            lines.append(
                f'cte_http_requests_total{{method="{_esc(method)}",path="{_esc(path)}"}} {value}'
            )
        lines.extend([
            "# HELP cte_http_responses_total Total HTTP responses by status.",
            "# TYPE cte_http_responses_total counter",
        ])
        for (status,), value in sorted(self.responses_total.items()):
            lines.append(
                f'cte_http_responses_total{{status="{status}"}} {value}'
            )
        lines.extend([
            "# HELP cte_http_request_duration_ms_sum Sum of HTTP request duration in milliseconds.",
            "# TYPE cte_http_request_duration_ms_sum counter",
            f"cte_http_request_duration_ms_sum {self.durations_ms_total:.3f}",
        ])
        return "\n".join(lines) + "\n"


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


METRICS = MetricsRegistry.create()
