"""Deterministic episode manager and responder lifecycle simulation."""
import asyncio

import numpy as np

from app.agents.fire import FireAgent
from app.agents.registry import AGENTS
from app.core.bus import EventBus, InMemoryBus
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
from app.config import Settings
from app.metrics.collector import MetricsCollector
from app.sim.grid_sim import GridSim
from app.sim.pune_sim import PuneSim
from app.sim.incidents import IncidentGenerator
from app.strategies.base import DispatchStrategy
from app.strategies.nearest import NearestStrategy


class SimulationManager:
    """Own one seeded simulation, responders, event bus, and metrics."""
    def __init__(self, seed: int = 1, duration_s: float = 3600, rate_per_minute: float = 2/3, bus: EventBus | None = None, strategy: DispatchStrategy | None = None, simulation_mode: str = "gridsim", data_dir=None) -> None:
        self.seed, self.duration_s, self.rate = seed, duration_s, rate_per_minute
        self.bus = bus or InMemoryBus()
        self.rng = np.random.default_rng(seed)
        if simulation_mode not in {"pune", "gridsim"}:
            raise ValueError("SIMULATION_MODE must be pune or gridsim")
        self.simulation_mode = simulation_mode
        self.sim = PuneSim(data_dir or Settings().pune_data_dir) if simulation_mode == "pune" else GridSim()
        self.sim.reset({}, self.rng)
        self.generator = IncidentGenerator(self.rng, rate_per_minute, network=self.sim if simulation_mode == "pune" else None)
        self.strategy = strategy or NearestStrategy()
        self.units: list[Unit] = []
        if simulation_mode == "pune":
            self.hospitals = [Hospital(id=poi["id"], name=poi["name"], location=LatLon(lat=poi["lat"], lon=poi["lon"]), beds_total=15, beds_free=15, icu_total=4, icu_free=4) for poi in self.sim.data["pois"] if poi["kind"] == "hospital"]
        else:
            self.hospitals = [Hospital(id=f"H{i + 1}", location=LatLon(lat=18.518 + i * .009, lon=73.854 + i * .008), beds_total=beds, beds_free=beds, icu_total=icu, icu_free=icu) for i, (beds, icu) in enumerate([(20, 4), (30, 8), (15, 3)])]
        self.sim._hospitals = self.hospitals
        self.stations: list[Station] = []
        pune_pois = self.sim.data["pois"] if simulation_mode == "pune" else []
        for kind, count, prefix in [(AgentKind.ambulance, 4, "A"), (AgentKind.fire, 3, "F"), (AgentKind.police, 3, "P")]:
            poi_kind = {AgentKind.ambulance: "hospital", AgentKind.fire: "fire_station", AgentKind.police: "police"}[kind]
            locations = [poi for poi in pune_pois if poi["kind"] == poi_kind]
            for index in range(count):
                poi = locations[index % len(locations)] if locations else None
                station_id = poi["id"] if poi else f"{prefix}S{index % 2 + 1}"
                loc = LatLon(lat=poi["lat"], lon=poi["lon"]) if poi else LatLon(lat=18.5204 + (index % 2) * .005, lon=73.8567 + (index // 2) * .006)
                unit_loc = self.sim._coordinate(self.sim._node(loc)) if simulation_mode == "pune" else loc
                self.units.append(Unit(id=f"{prefix}{index + 1}", kind=kind, station_id=station_id, location=unit_loc))
                if not any(s.id == station_id for s in self.stations):
                    self.stations.append(Station(id=station_id, kind=kind, location=loc))
        self.incidents: list[Incident] = []
        self.decisions: list[dict[str, object]] = []
        self.metrics = MetricsCollector()
        self.paused = False
        self.stopped = False
        self._active: dict[str, dict[str, object]] = {}
        self.hospital_rejections = 0
        self._response_recorded: set[str] = set()
        self.unit_events: list[dict[str, object]] = []
        self.metric_snapshots: list[dict[str, object]] = []
        self.agents = {
            kind: AGENTS[kind](kind, [unit for unit in self.units if unit.kind == kind], self.bus)
            for kind in (AgentKind.ambulance, AgentKind.fire, AgentKind.police)
        }
        self.hospital_agent = AGENTS[AgentKind.hospital](AgentKind.hospital, [], self.bus)

    async def emit(self, event: Event) -> None:
        """Publish an event and drain inline for deterministic runs."""
        if self.bus:
            if event.type.startswith("incident."):
                stream = "incidents"
            elif event.type.startswith("hospital."):
                stream = "hospital"
            elif event.type == "decision.logged":
                stream = "agents"
            elif event.type.startswith("unit.") or event.type == "corridor.cleared":
                stream = "dispatch"
            else:
                stream = "sim"
            await self.bus.publish(stream, event)
            await self.bus.drain()

    async def run_episode(self, tick_s: float = 5.0, realtime: bool = False, speed: float = 1.0) -> dict[str, object]:
        """Run until the configured duration, processing arrivals and resources."""
        while self.sim.sim_time < self.duration_s and not self.stopped:
            if self.paused:
                await asyncio.sleep(.01)
                continue
            self.sim.step(tick_s)
            if realtime:
                await asyncio.sleep(.025 / max(speed, .01))
            for incident in self.generator.due(self.sim.sim_time, self.sim.origin, self.sim if self.simulation_mode == "pune" else None):
                self.incidents.append(incident)
                self.metrics.incidents += 1
                await self.emit(make_event("incident.created", self.sim.sim_time, "generator", incident=incident.model_dump(mode="json")))
            pending = sorted((i for i in self.incidents if i.status == IncidentStatus.pending), key=lambda i: (-i.severity, i.created_at))
            await self._dispatch_pending_batch(pending)
            old_status = {unit.id: unit.status for unit in self.units}
            await self._advance_units(tick_s)
            for unit in self.units:
                if unit.kind == AgentKind.police:
                    self.sim.set_corridor_cleared(unit.id, unit.status == UnitStatus.en_route)
                    if old_status[unit.id] == UnitStatus.en_route and unit.status != UnitStatus.en_route:
                        await self.emit(make_event("corridor.cleared", self.sim.sim_time, "police", unit_id=unit.id, cleared=False))
                if old_status[unit.id] != unit.status:
                    unit_event = {"unit_id": unit.id, "status": unit.status.value, "incident_id": unit.assigned_incident_id, "sim_time": self.sim.sim_time}
                    self.unit_events.append(unit_event)
                    await self.emit(make_event("unit.status_changed", self.sim.sim_time, "manager", unit_id=unit.id, status=unit.status.value, incident_id=unit.assigned_incident_id))
            if int(self.sim.sim_time) % 30 == 0:
                self.metric_snapshots.append(self._metric_snapshot())
        self.metrics.queued_end = sum(i.status == IncidentStatus.pending for i in self.incidents)
        if not self.metric_snapshots or self.metric_snapshots[-1]["sim_time"] != self.sim.sim_time:
            self.metric_snapshots.append(self._metric_snapshot())
        return self.result()

    def _metric_snapshot(self) -> dict[str, object]:
        """Capture a persisted 30-second metric record."""
        return self.dashboard_metrics() | {
            "sim_time": self.sim.sim_time,
            "queued": sum(incident.status == IncidentStatus.pending for incident in self.incidents),
        }

    def dashboard_metrics(self) -> dict[str, object]:
        """Return rolling response and utilization metrics for dashboard clients."""
        counts = self.resource_counts()
        utilization = {
            kind: self.metrics.busy_time[kind] / max(1, self.sim.sim_time * count)
            for kind, count in counts.items()
        }
        return self.metrics.snapshot(self.sim.sim_time, self.sim.mean_traffic_delay()) | {"utilization": utilization}

    def agent_snapshot(self) -> dict[str, dict[str, object]]:
        """Return each agent's idle/busy resources and most recent action."""
        summary: dict[str, dict[str, object]] = {}
        for kind, agent in self.agents.items():
            idle = len(agent.idle_units())
            summary[kind.value] = {"idle": idle, "busy": len(agent.units) - idle, "last_action": agent.last_action}
        summary[AgentKind.hospital.value] = {
            "beds_free": sum(hospital.beds_free for hospital in self.hospitals),
            "icu_free": sum(hospital.icu_free for hospital in self.hospitals),
            "last_action": self.hospital_agent.last_action,
        }
        return summary

    def resource_counts(self) -> dict[str, int]:
        """Return responder counts for utilization denominators."""
        return {kind.value: sum(unit.kind == kind for unit in self.units) for kind in (AgentKind.ambulance, AgentKind.fire, AgentKind.police)}

    async def _dispatch_pending_batch(self, incidents: list[Incident]) -> None:
        """Optimize assignments jointly across all incidents pending this tick."""
        selections: dict[str, dict[AgentKind, list[object]]] = {i.id: {} for i in incidents}
        order = {AgentKind.police: 0, AgentKind.ambulance: 1, AgentKind.fire: 2}
        for kind in sorted(self.agents, key=lambda k: order[k]):
            demands: list[Incident] = []
            for incident in incidents:
                if kind not in incident.requires:
                    continue
                need = FireAgent.required_units(incident) if kind == AgentKind.fire else 1
                already = sum(1 for d in self.decisions if d.get('incident_id') == incident.id and d.get('kind') == kind.value)
                demands.extend([incident] * max(0, need - already))
            agent = self.agents[kind]
            selected = self.strategy.select_batch(demands, agent.idle_units(), self.sim)
            for decision in selected:
                selections[decision.incident_id].setdefault(kind, []).append(decision)
        for incident in incidents:
            await self._dispatch(incident, selections.get(incident.id, {}))

    async def _dispatch(self, incident: Incident, batch: dict[AgentKind, list[object]] | None = None) -> None:
        """Assign nearest idle required responders or queue the incident."""
        dispatch_order = {AgentKind.police: 0, AgentKind.ambulance: 1, AgentKind.fire: 2}
        for kind in sorted(incident.requires, key=lambda k: dispatch_order[k]):
            needed = FireAgent.required_units(incident) if kind == AgentKind.fire else 1
            already = sum(1 for decision in self.decisions if decision.get("incident_id") == incident.id and decision.get("kind") == kind.value)
            agent = self.agents[kind]
            selections = batch.get(kind, []) if batch is not None else agent.select_for_incident(incident, self.sim, self.strategy, max(0, needed - already))
            for decision in selections:
                idle = [unit for unit in agent.idle_units() if unit.id == decision.unit_id]
                unit = next(u for u in idle if u.id == decision.unit_id)
                unit.status, unit.assigned_incident_id = UnitStatus.en_route, incident.id
                agent.last_action = decision.chosen_reason
                self.sim.dispatch_unit(unit.id, incident.location, emergency=True)
                await self.emit(make_event("unit.dispatched", self.sim.sim_time, kind.value, unit_id=unit.id, incident_id=incident.id, eta_s=decision.eta_s))
                if kind == AgentKind.police:
                    self.sim.set_corridor_cleared(unit.id, True)
                    await self.emit(make_event("corridor.cleared", self.sim.sim_time, kind.value, unit_id=unit.id, incident_id=incident.id))
                record = decision.model_dump(mode="json") | {"kind": kind.value, "explanation": f"{kind.value.title()} {decision.chosen_reason}"}
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
                self.metrics.busy_time[unit.kind.value] += dt
                unit.location = self.sim.unit_position(unit.id)
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
                    self._active[unit.id] = {"service": max(30, incident.severity * 45)}
                    response = max(0, self.sim.sim_time - incident.created_at)
                    if incident.id not in self._response_recorded:
                        self.metrics.response_times.append(response)
                        self.metrics.by_type[incident.type.value].append(response)
                        self.metrics.by_severity[str(incident.severity)].append(response)
                        self._response_recorded.add(incident.id)
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
                    if incident.severity >= 4:
                        hospital.icu_free = min(hospital.icu_total, hospital.icu_free + 1)
                    unit.status = UnitStatus.returning
                    unit.assigned_incident_id = f"return:{unit.station_id}"
                    station = next(s for s in self.stations if s.id == unit.station_id)
                    self.sim.dispatch_unit(unit.id, station.location, emergency=False)
        for incident in self.incidents:
            if (
                incident.status != IncidentStatus.resolved
                and all(
                    sum(1 for decision in self.decisions if decision.get("incident_id") == incident.id and decision.get("kind") == kind.value)
                    >= (2 if kind == AgentKind.fire and incident.severity >= 4 else 1)
                    and not any(u.assigned_incident_id == incident.id and u.kind == kind for u in self.units)
                    for kind in incident.requires
                )
                and self.sim.sim_time > incident.created_at
                and any(d["incident_id"] == incident.id for d in self.decisions)
            ):
                incident.status = IncidentStatus.resolved
                await self.emit(make_event("incident.resolved", self.sim.sim_time, "manager", incident_id=incident.id))

    async def _allocate_hospital(self, incident: Incident) -> Hospital | None:
        """Reserve the nearest hospital with bed and severity-required ICU capacity."""
        await self.emit(make_event("hospital.bed_request", self.sim.sim_time, "ambulance", incident_id=incident.id, severity=incident.severity, requires_icu=incident.severity >= 4))
        hospital = self.hospital_agent.select_hospital(incident, self.hospitals, self.sim)
        if hospital is not None:
            eta_s, _ = self.sim.travel_time(incident.location, hospital.location, emergency=True)
            explanation = f"{hospital.id} selected: ETA {eta_s / 60:.1f} min, {hospital.beds_free} beds and {hospital.icu_free} ICU beds free."
            self.hospital_agent.last_action = explanation
            await self.emit(make_event("hospital.bed_response", self.sim.sim_time, "hospital", incident_id=incident.id, hospital_id=hospital.id, accepted=True, beds_free=hospital.beds_free, icu_free=hospital.icu_free, eta_s=eta_s, explanation=explanation))
            return hospital
        self.hospital_rejections += 1
        self.hospital_agent.last_action = "No hospital has the required bed capacity"
        await self.emit(make_event("hospital.bed_response", self.sim.sim_time, "hospital", incident_id=incident.id, accepted=False, reason="No suitable bed available"))
        return None

    def result(self) -> dict[str, object]:
        """Return a stable JSON-like run record."""
        return {"seed": self.seed, "sim_time": self.sim.sim_time, "incidents": [i.model_dump(mode="json") for i in self.incidents], "decisions": self.decisions, "unit_events": self.unit_events, "metric_snapshots": self.metric_snapshots, "hospitals": [hospital.model_dump(mode="json") for hospital in self.hospitals], "metrics": self.metrics.summary(self.duration_s, self.sim.mean_traffic_delay(), self.resource_counts()) | {"hospital_rejections": self.hospital_rejections}}
