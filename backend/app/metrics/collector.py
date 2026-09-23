"""Episode response and utilization metrics."""
from collections import defaultdict


class MetricsCollector:
    """Collect deterministic completion statistics for one episode."""
    def __init__(self) -> None:
        self.response_times: list[float] = []
        self.by_type: dict[str, list[float]] = defaultdict(list)
        self.busy_time: dict[str, float] = defaultdict(float)
        self.decisions: list[dict[str, object]] = []
        self.queued_end = 0
        self.incidents = 0

    def snapshot(self, sim_time: float, traffic_delay: float) -> dict[str, object]:
        """Return current average response and traffic metrics."""
        del sim_time
        avg = sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
        return {"avg_response_s": avg, "traffic_delay_s": traffic_delay, "queued": self.queued_end}

    def summary(self, duration_s: float, traffic_delay: float, unit_counts: dict[str, int]) -> dict[str, object]:
        """Return export-ready episode metrics."""
        responses = sorted(self.response_times)
        p95 = responses[min(len(responses) - 1, int(.95 * len(responses)))] if responses else 0.0
        utilization = {kind: self.busy_time[kind] / max(1, duration_s * count) for kind, count in unit_counts.items()}
        return {"incidents": self.incidents, "avg_response_s": sum(responses) / len(responses) if responses else 0.0, "p95_response_s": p95, "ambulance_util": utilization.get("ambulance", 0.0), "fire_util": utilization.get("fire", 0.0), "police_util": utilization.get("police", 0.0), "mean_traffic_delay_s": traffic_delay, "queued_end": self.queued_end}
