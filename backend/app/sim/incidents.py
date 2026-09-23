"""Seeded Poisson incident generation and response requirement rules."""
import numpy as np

from app.core.models import AgentKind, Incident, IncidentType, LatLon


def requirements(kind: IncidentType, severity: int, injuries: bool) -> set[AgentKind]:
    """Map incident attributes to required responder kinds."""
    if kind == IncidentType.accident:
        result = {AgentKind.police}
        if severity >= 2 or injuries:
            result.add(AgentKind.ambulance)
        if severity >= 4:
            result.add(AgentKind.fire)
        return result
    if kind == IncidentType.fire:
        result = {AgentKind.fire}
        if injuries:
            result.add(AgentKind.ambulance)
        if severity >= 3:
            result.add(AgentKind.police)
        return result
    return {AgentKind.ambulance}


class IncidentGenerator:
    """Generate seeded Poisson arrivals uniformly on the city grid."""
    def __init__(self, rng: np.random.Generator, rate_per_minute: float, size: int = 8, block_m: float = 250, network: object | None = None) -> None:
        self.rng, self.rate, self.size, self.block_m, self.network = rng, rate_per_minute, size, block_m, network
        self.next_at = float(rng.exponential(60 / rate_per_minute)) if rate_per_minute > 0 else float("inf")
        self.counter = 0

    def due(self, sim_time: float, origin: LatLon, network: object | None = None) -> list[Incident]:
        """Create all incidents whose scheduled time has arrived."""
        items: list[Incident] = []
        while self.next_at <= sim_time:
            self.counter += 1
            kind = IncidentType(str(self.rng.choice([e.value for e in IncidentType])))
            severity = int(self.rng.integers(1, 6))
            injuries = bool(self.rng.random() < 0.45)
            active_network = network or self.network
            if active_network is not None and hasattr(active_network, 'sample_location'):
                location = active_network.sample_location(self.rng)
            else:
                lat = origin.lat + int(self.rng.integers(0, self.size)) * self.block_m / 111_320
                lon = origin.lon + int(self.rng.integers(0, self.size)) * self.block_m / (111_320 * 0.95)
                location = LatLon(lat=lat, lon=lon)
            items.append(Incident(id=f"I{self.counter}", type=kind, severity=severity, location=location, created_at=self.next_at, requires=requirements(kind, severity, injuries), injuries=injuries))
            self.next_at += float(self.rng.exponential(60 / self.rate)) if self.rate > 0 else float("inf")
        return items
