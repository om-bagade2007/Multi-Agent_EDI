"""Deterministic episode manager and responder lifecycle simulation."""
import asyncio

import numpy as np

from app.core.bus import EventBus
from app.core.events import Event, make_event
from app.core.models import (
    AgentKind,
    Hospital,
    Incident,
    IncidentStatus,
    LatLon,
    Station,
    Unit,
    UnitStatus,
)
from app.metrics.collector import MetricsCollector
from app.sim.grid_sim import GridSim
from app.sim.incidents import IncidentGenerator
from app.strategies.nearest import NearestStrategy


class SimulationManager:
    """Own one seeded simulation, responders, event bus, and metrics."""
    def __init__(self, seed: int = 1, duration_s: float = 3600, rate_per_minute: float = 2/3, bus: EventBus | None = None) -> None:
        self.seed, self.duration_s, self.rate = seed, duration_s, rate_per_minute
        self.bus = bus
        self.rng = np.random.default_rng(seed)
        self.sim = GridSim()
        self.sim.reset({}, self.rng)
        self.generator = IncidentGenerator(self.rng, rate_per_minute)
        self.strategy = NearestStrategy()
        self.units: list[Unit] = []
        self.hospitals = [
            Hospital(id=f"H{i + 1}", location=LatLon(lat=18.518 + i * .009, lon=73.854 + i * .008), beds_total=beds, beds_free=beds, icu_total=icu, icu_free=icu)
            for i, (beds, icu) in enumerate([(20, 4), (30, 8), (15, 3)])
        ]
        self.stations: list[Station] = []
        for kind, count, prefix in [(AgentKind.ambulance, 4, "A"), (AgentKind.fire, 3, "F"), (AgentKind.police, 3, "P")]:
            for index in range(count):
                station_id = f"{prefix}S{index % 2 + 1}"
                loc = LatLon(lat=18.5204 + (index % 2) * .005, lon=73.8567 + (index // 2) * .006)
                self.units.append(Unit(id=f"{prefix}{index + 1}", kind=kind, station_id=station_id, location=loc))
                if not any(s.id == station_id for s in self.stations):
                    self.stations.append(Station(id=station_id, kind=kind, location=loc))
        self.incidents: list[Incident] = []
        self.decisions: list[dict[str, object]] = []
        self.metrics = MetricsCollector()
        self.paused = False
        self.stopped = False
        self._active: dict[str, dict[str, object]] = {}
        self.hospital_rejections = 0

    async def emit(self, event: Event) -> None:
        """Publish an event and drain inline for deterministic runs."""
        if self.bus:
            await self.bus.publish("sim", event)
            await self.bus.drain()

    async def run_episode(self, tick_s: float = 5.0, realtime: bool = False) -> dict[str, object]:
        """Run until the configured duration, processing arrivals and resources."""
        while self.sim.sim_time < self.duration_s and not self.stopped:
            if self.paused:
                await asyncio.sleep(.01)
                continue
            self.sim.step(tick_s)
            if realtime:
                await asyncio.sleep(.025)
            for incident in self.generator.due(self.sim.sim_time, self.sim.origin):
                self.incidents.append(incident)
                self.metrics.incidents += 1
                await self.emit(make_event("incident.created", self.sim.sim_time, "generator", incident=incident.model_dump(mode="json")))
                await self._dispatch(incident)
            for incident in sorted((i for i in self.incidents if i.status == IncidentStatus.pending), key=lambda i: (-i.severity, i.created_at)):
                await self._dispatch(incident)
            old_status = {unit.id: unit.status for unit in self.units}
            await self._advance_units(tick_s)
            for unit in self.units:
                if old_status[unit.id] != unit.status:
                    await self.emit(make_event("unit.status_changed", self.sim.sim_time, "manager", unit_id=unit.id, status=unit.status.value, incident_id=unit.assigned_incident_id))
        self.metrics.queued_end = sum(i.status == IncidentStatus.pending for i in self.incidents)
        return self.result()

    async def _dispatch(self, incident: Incident) -> None:
        """Assign nearest idle required responders or queue the incident."""
        for kind in sorted(incident.requires, key=lambda k: k.value):
            needed = 2 if kind == AgentKind.fire and incident.severity >= 4 else 1
            already = sum(1 for unit in self.units if unit.assigned_incident_id == incident.id and unit.kind == kind)
            for _ in range(max(0, needed - already)):
                idle = [u for u in self.units if u.kind == kind and u.status == UnitStatus.idle]
                decision = self.strategy.select_unit(incident, idle, self.sim)
                if decision is None:
                    continue
                unit = next(u for u in idle if u.id == decision.unit_id)
                unit.status, unit.assigned_incident_id = UnitStatus.en_route, incident.id
                self.sim.dispatch_unit(unit.id, incident.location, emergency=True)
                record = decision.model_dump(mode="json") | {"explanation": f"{kind.value.title()} {decision.chosen_reason}"}
                self.decisions.append(record)
                self.metrics.decisions.append(record)
                await self.emit(make_event("decision.logged", self.sim.sim_time, kind.value, decision=record))
            if sum(1 for u in self.units if u.assigned_incident_id == incident.id and u.kind == kind) < needed:
                await self.emit(make_event("incident.queued", self.sim.sim_time, "manager", incident_id=incident.id, kind=kind.value))
        if all(any(u.assigned_incident_id == incident.id and u.kind == k for u in self.units) for k in incident.requires):
            incident.status = IncidentStatus.dispatched

    async def _advance_units(self, dt: float) -> None:
        """Advance each unit through travel, service and return states."""
        for unit in self.units:
            if unit.status == UnitStatus.idle or not unit.assigned_incident_id:
                continue
            if unit.status == UnitStatus.returning:
                if self.sim.unit_arrived(unit.id):
                    station = next(s for s in self.stations if s.id == unit.station_id)
                    unit.location, unit.status, unit.assigned_incident_id = station.location, UnitStatus.idle, None
                    self._active.pop(unit.id, None)
                continue
            incident = next(i for i in self.incidents if i.id == unit.assigned_incident_id)
            self.metrics.busy_time[unit.kind.value] += dt
            if unit.status == UnitStatus.en_route:
                unit.location = self.sim.unit_position(unit.id)
                if self.sim.unit_arrived(unit.id):
                    unit.status = UnitStatus.on_scene
                    self._active[unit.id] = {"service": max(30, incident.severity * 45), "response_recorded": False}
                    response = max(0, self.sim.sim_time - incident.created_at)
                    if not self._active[unit.id]["response_recorded"]:
                        self.metrics.response_times.append(response)
                        self.metrics.by_type[incident.type.value].append(response)
                        self._active[unit.id]["response_recorded"] = True
                    incident.status = IncidentStatus.on_scene
            elif unit.status == UnitStatus.on_scene:
                remaining = float(self._active[unit.id]["service"]) - dt
                self._active[unit.id]["service"] = remaining
                if remaining <= 0:
                    if unit.kind == AgentKind.ambulance and incident.injuries:
                        hospital = await self._allocate_hospital(incident)
                        if hospital is not None:
                            unit.status = UnitStatus.transporting
                            self._active[unit.id]["hospital_id"] = hospital.id
                            self.sim.dispatch_unit(unit.id, hospital.location, emergency=True)
                        else:
                            unit.status = UnitStatus.returning
                            unit.assigned_incident_id = f"return:{unit.station_id}"
                            station = next(s for s in self.stations if s.id == unit.station_id)
                            self.sim.dispatch_unit(unit.id, station.location, emergency=False)
                    else:
                        unit.status = UnitStatus.returning
                        unit.assigned_incident_id = f"return:{unit.station_id}"
                        station = next(s for s in self.stations if s.id == unit.station_id)
                        self.sim.dispatch_unit(unit.id, station.location, emergency=False)
            elif unit.status == UnitStatus.transporting:
                unit.location = self.sim.unit_position(unit.id)
                if self.sim.unit_arrived(unit.id):
                    unit.status = UnitStatus.at_hospital
                    self._active[unit.id]["stay"] = 300.0
            elif unit.status == UnitStatus.at_hospital:
                remaining = float(self._active[unit.id].get("stay", 0.0)) - dt
                self._active[unit.id]["stay"] = remaining
                if remaining <= 0:
                    hospital_id = str(self._active[unit.id].get("hospital_id", ""))
                    hospital = next(h for h in self.hospitals if h.id == hospital_id)
                    hospital.beds_free = min(hospital.beds_total, hospital.beds_free + 1)
                    if incident.severity >= 3:
                        hospital.icu_free = min(hospital.icu_total, hospital.icu_free + 1)
                    unit.status = UnitStatus.returning
                    unit.assigned_incident_id = f"return:{unit.station_id}"
                    station = next(s for s in self.stations if s.id == unit.station_id)
                    self.sim.dispatch_unit(unit.id, station.location, emergency=False)
        for incident in self.incidents:
            if (
                incident.status != IncidentStatus.resolved
                and all(
                    any(u.assigned_incident_id == incident.id and u.kind == kind for u in self.units)
                    is False
                    for kind in incident.requires
                )
                and self.sim.sim_time > incident.created_at
                and any(d["incident_id"] == incident.id for d in self.decisions)
            ):
                incident.status = IncidentStatus.resolved

    async def _allocate_hospital(self, incident: Incident) -> Hospital | None:
        """Reserve the nearest hospital with bed and severity-required ICU capacity."""
        ranked = sorted(self.hospitals, key=lambda hospital: self.sim.travel_time(incident.location, hospital.location, emergency=True)[0])
        for hospital in ranked:
            if hospital.beds_free > 0 and (incident.severity < 3 or hospital.icu_free > 0):
                hospital.beds_free -= 1
                if incident.severity >= 3:
                    hospital.icu_free -= 1
                await self.emit(make_event("hospital.bed_response", self.sim.sim_time, "hospital", incident_id=incident.id, hospital_id=hospital.id, accepted=True, beds_free=hospital.beds_free, icu_free=hospital.icu_free))
                return hospital
        self.hospital_rejections += 1
        await self.emit(make_event("hospital.bed_response", self.sim.sim_time, "hospital", incident_id=incident.id, accepted=False, reason="No suitable bed available"))
        return None

    def result(self) -> dict[str, object]:
        """Return a stable JSON-like run record."""
        return {"seed": self.seed, "sim_time": self.sim.sim_time, "incidents": [i.model_dump(mode="json") for i in self.incidents], "decisions": self.decisions, "hospitals": [hospital.model_dump(mode="json") for hospital in self.hospitals], "metrics": self.metrics.summary(self.duration_s, self.sim.mean_traffic_delay(), {"ambulance": 4, "fire": 3, "police": 3}) | {"hospital_rejections": self.hospital_rejections}}
