Codex Prompt — Urban Emergency Response Simulation (Stage 1 ≈ 30%)

How to use: paste everything below the line into Codex as one task, or run each PHASE (0–7) as its own task in order. Keep the whole document in the repo as docs/TASK_STAGE1.md.

ROLE

You are a senior full-stack + ML engineer. Build Stage 1 of a university research project: a software-only, multi-agent urban emergency response simulator with a live dashboard. Stage 1 is a complete, runnable vertical slice with a nearest-resource baseline. Later stages (A*/Hungarian optimisation, MAPPO) will plug into it, so design the extension points properly.

PROJECT CONTEXT

Project: AI-Powered Multi-Agent Software Simulation for Urban Emergency Response. A virtual city (roads, intersections, hospitals, fire/police/ambulance stations) is simulated. Four cooperating software agents — Ambulance, Fire & Rescue, Police & Traffic, Hospital Resource — receive incidents over an event bus, communicate, and make dispatch decisions. Every decision comes with a human-readable explanation. A React dashboard shows everything live. Researchers compare dispatch strategies on response time, resource utilisation and traffic delay.

Final project stack (respect it): Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, PostgreSQL + PostGIS, Redis Streams, SUMO + TraCI (OpenStreetMap data), Gymnasium/PettingZoo (later), React + TypeScript + Vite + Tailwind + MapLibre GL JS + Recharts, Docker + Docker Compose.

SCOPE OF THIS TASK

In scope (Stage 1):

Monorepo scaffold, tooling, Docker Compose, Makefile, CI-style test commands.
Domain models and event envelope; event bus with Redis Streams implementation and an in-memory implementation with the same interface.
Simulation backend interface with two implementations: GridSim (pure Python, default, deterministic) and SumoBackend (TraCI, best-effort, optional).
Incident generator (seeded, Poisson arrivals, types and severities).
Four agents with a nearest-resource baseline strategy, hospital capacity handling, police corridor clearing, and explanations.
Persistence (SQLAlchemy) and metrics collection.
FastAPI REST + WebSocket API.
React command dashboard.
Experiment CLI that runs seeded episodes for the baseline and writes CSV.
Tests, README, docs.

Out of scope (do NOT build; leave only the Protocol/interface stubs described below): A*/Hungarian strategy, MAPPO/RL training, PettingZoo env, failure-recovery experiments, drones, weather agent, citizen agent, digital-twin sync with live data, auth/RBAC, Kubernetes/cloud deployment.

OPERATING RULES
Do not stop to ask questions. When something is ambiguous, pick the simplest reasonable option and record it in docs/DECISIONS.md (one bullet each: decision + reason).
Work phase by phase. After each phase: run its verification commands, fix failures, then commit (git commit -m "phase N: <summary>").
Everything in-scope must run with no SUMO, no GPU, no internet, no API keys. Defaults: GridSim, InMemoryBus, SQLite. Docker Compose switches to Redis + Postgres/PostGIS. SUMO is opt-in via env var.
Determinism: all randomness comes from a numpy.random.Generator created from the run seed and passed explicitly. Same seed + same config ⇒ identical metrics. Add a test for this.
Python: type hints everywhere, Pydantic v2 models, ruff + pytest (+ pytest-asyncio). TypeScript: strict: true, no any.
No TODO placeholders inside in-scope features. Out-of-scope items are only Protocols/abstract classes with docstrings.
Small, focused modules; no file over ~300 lines. Docstrings on public classes/functions.
Create AGENTS.md at the repo root containing these operating rules plus the commands from “Verification commands”.
REPO LAYOUT
urban-emergency-sim/
├─ AGENTS.md
├─ README.md
├─ Makefile
├─ docker-compose.yml
├─ .env.example
├─ docs/  (DECISIONS.md, ARCHITECTURE.md, TASK_STAGE1.md)
├─ scenarios/
│  └─ default.yaml
├─ sumo/
│  ├─ build_grid_net.sh        # netgenerate fallback network
│  ├─ build_osm_net.sh         # OSM bbox -> netconvert (configurable bbox)
│  └─ README.md
├─ backend/
│  ├─ pyproject.toml
│  ├─ Dockerfile
│  ├─ app/
│  │  ├─ main.py               # FastAPI app factory
│  │  ├─ config.py             # pydantic-settings
│  │  ├─ core/   models.py events.py bus.py geo.py scenario.py
│  │  ├─ sim/    base.py grid_sim.py sumo_sim.py incidents.py manager.py
│  │  ├─ agents/ base.py ambulance.py fire.py police.py hospital.py registry.py
│  │  ├─ strategies/ base.py nearest.py      # DispatchStrategy Protocol + baseline
│  │  ├─ db/     session.py tables.py repository.py
│  │  ├─ metrics/ collector.py
│  │  └─ api/    routes.py ws.py schemas.py
│  ├─ experiments/run_experiment.py
│  └─ tests/
└─ frontend/
   ├─ package.json  vite.config.ts  tailwind.config.ts  Dockerfile
   └─ src/ (main.tsx, App.tsx, types.ts, hooks/, components/, lib/)
PHASE 0 — Scaffold & tooling
Create the layout above, pyproject.toml (fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, psycopg[binary], redis, numpy, networkx, pyyaml, pandas; dev: pytest, pytest-asyncio, httpx, ruff), Vite React TS app with Tailwind, MapLibre GL, Recharts.
Makefile targets: install, backend, frontend, test, lint, demo, experiment, up, down.
docker-compose.yml: services redis, db (image postgis/postgis), backend, frontend. SUMO is not a required service.
.env.example: SIM_BACKEND=grid|sumo, BUS=memory|redis, DATABASE_URL, REDIS_URL, SUMO_HOME.

Verify: make install && make lint && make test (a trivial health-check test) pass.

PHASE 1 — Domain models & event bus

Models (core/models.py, Pydantic v2):

LatLon, Incident {id, type: accident|fire|medical, severity 1–5, location, created_at, requires: set[AgentKind], injuries: bool, status: pending|dispatched|on_scene|resolved}.
Unit {id, kind: ambulance|fire|police, station_id, location, status: idle|en_route|on_scene|transporting|at_hospital|returning, assigned_incident_id}.
Station {id, kind, location}, Hospital {id, location, beds_total, beds_free, icu_total, icu_free}.
DispatchDecision {id, incident_id, unit_id, eta_s, chosen_reason: str, candidates: list[{unit_id, eta_s, distance_m}], strategy: str, sim_time} — keep candidates so future strategies can be compared.

Incident requirements rule (in incidents.py):

accident → police always; ambulance if severity ≥ 2 or injuries; fire if severity ≥ 4
fire → fire always; ambulance if injuries; police if severity ≥ 3
medical → ambulance only

Events (core/events.py): envelope {id, type, sim_time, wall_time, source, payload}. Types: incident.created, incident.queued, unit.dispatched, unit.status_changed, hospital.bed_request, hospital.bed_response, corridor.cleared, incident.resolved, decision.logged.

Bus (core/bus.py): abstract EventBus with publish(stream, event), subscribe(stream, group, consumer, handler), drain().

InMemoryBus: asyncio-based, drain() processes all pending handlers to completion (used for deterministic headless runs and tests).
RedisStreamsBus: XADD / XREADGROUP, one consumer group per agent, maxlen≈10000, ack after handling.
Streams: incidents, dispatch, hospital, agents, sim.

Verify: unit tests — publish/subscribe ordering, drain semantics, Redis bus tested only if REDIS_URL reachable (else skipped).

PHASE 2 — Simulation backends

sim/base.py: SimBackend Protocol:

reset(scenario, rng) -> None
step(dt: float = 1.0) -> None
sim_time -> float
travel_time(origin: LatLon, dest: LatLon, *, emergency: bool) -> tuple[float, float]  # (seconds, meters)
dispatch_unit(unit_id, dest: LatLon, *, emergency: bool) -> None   # starts movement
unit_position(unit_id) -> LatLon
unit_arrived(unit_id) -> bool
set_corridor_cleared(unit_id, cleared: bool) -> None
traffic_snapshot() -> list[EdgeState]      # id, geometry, congestion 0–1
mean_traffic_delay() -> float              # extra seconds vs free flow

GridSim (default):

N×N intersection grid (default 8×8, 250 m blocks) mapped to lat/lon around a configurable origin. networkx graph; edge travel time = length / (free_speed * congestion(t, edge)).
congestion in [0.35, 1.0]: smooth time-varying pattern (rush-hour sinusoid + per-edge seeded noise), all from the run RNG.
Emergency vehicles: ×1.3 speed; ×1.2 more while corridor is cleared (both configurable in scenario).
Units move along the Dijkstra path by current travel times; positions interpolated per tick for the dashboard.
Deterministic and fast (a 1-hour sim episode should run in a few seconds headless).

SumoBackend (best effort, must not block other work):

Implements the same Protocol via TraCI; emergency vehicles use an emergency vType; corridor clearing sets speed factor / temporary traffic-light priority.
sumo/build_grid_net.sh (netgenerate) and sumo/build_osm_net.sh (OSM bbox from env, default a small area of Pune, via netconvert) plus a sumo/README.md.
Enabled only when SIM_BACKEND=sumo and SUMO_HOME is set. Its smoke test is skipped if SUMO is not installed.

Scenario (scenarios/default.yaml): origin, grid size, 4 ambulances (2 stations), 3 fire trucks (2 stations), 3 police units (2 stations), 3 hospitals (beds 20/30/15, ICU 4/8/3), incident rate (default 1 per 90 s), duration (default 3600 s), service times by severity, speed multipliers.

Verify: tests — Dijkstra ETA sanity, movement reaches destination, same seed ⇒ identical traffic snapshots, emergency ETA < normal ETA.

PHASE 3 — Agents & baseline strategy

strategies/base.py: DispatchStrategy Protocol: select_unit(incident, idle_units, sim) -> DispatchDecision | None. Also add a documented abstract HospitalSelector Protocol. Do not implement Hungarian/MAPPO — just note in docstrings where they will plug in.

strategies/nearest.py: picks the idle unit with the smallest travel-time ETA (not straight-line distance). Records every candidate in DispatchDecision.candidates.

Agents (agents/): each agent subscribes to the bus, owns its units, and reacts to events. Base class handles subscribe/publish/logging.

Ambulance Agent: on incident.created where AgentKind.ambulance ∈ requires → strategy picks unit → publishes unit.dispatched. On arrival and treatment, sends hospital.bed_request (severity ≥ 3 requests ICU). On hospital.bed_response → transports patient, then returns to station.
Hospital Resource Agent: owns Hospital objects; on bed request, accepts the nearest hospital (by ETA from the incident) with free capacity, otherwise the next nearest; decrements beds; frees beds after a configurable stay time. Publishes hospital.bed_response with the reasoning.
Fire & Rescue Agent: dispatches nearest fire unit(s); a severity ≥ 4 incident requires 2 units.
Police & Traffic Agent: dispatches nearest police unit and publishes corridor.cleared for every emergency vehicle en route, which calls sim.set_corridor_cleared. Corridor clearing only applies while a unit is en route.
Queueing: if no idle unit exists, publish incident.queued; the manager retries queued incidents each tick by severity (highest first, then oldest).
Unit lifecycle: idle → en_route → on_scene (service time by severity) → [ambulance: transporting → at_hospital] → returning → idle. Each transition emits unit.status_changed.
Explanations: every decision includes text such as: "Ambulance A2 selected: ETA 4.8 min, fastest of 3 idle ambulances (next best A1: 6.1 min). Hospital H2 selected: 12 beds and 3 ICU free, ETA 5.2 min." Build it from the structured candidates, never hard-code strings for specific IDs.

sim/manager.py (SimulationManager): owns the tick loop: sim.step → incident generator → publish events → bus.drain() (for InMemoryBus) → agents update lifecycles → collect metrics. Supports pause/resume/stop and a speed multiplier when running live. Redis mode runs agents as background consumers.

Verify: tests — each incident type routes to the right agents; queueing when all ambulances are busy; hospital falls back to the next when full; the explanation string contains chosen and runner-up ETAs; full-episode determinism test; all incidents eventually resolve or remain queued at the end with correct counts.

PHASE 4 — Persistence & metrics
SQLAlchemy 2.0 tables: runs, incidents, dispatches (explanation + candidates JSON), unit_events, metric_snapshots. Repository layer with a session dependency. Default SQLite; Postgres/PostGIS via DATABASE_URL. Store locations as lat/lon floats (enable the postgis extension in the Compose init script for later use).
MetricsCollector: per-incident response time (created → first required unit on scene), per-type and per-severity means/p50/p95, resource utilisation (busy time ÷ total time per unit kind), mean traffic delay (from SimBackend), queued count, hospital rejections.
Metrics snapshot every 30 sim seconds and at the end of the run.

Verify: tests using SQLite — a full seeded episode persists and re-queries correctly; metric calculations match hand-computed fixtures.

PHASE 5 — API & WebSocket
GET /health, GET /scenario
POST /runs {strategy: "nearest", seed, incident_rate, duration_s, speed} → starts a live run (one active live run at a time; a second returns 409)
POST /runs/{id}/pause|resume|stop
GET /runs/{id}/metrics, GET /runs/{id}/decisions, GET /runs
WS /ws/runs/{id} pushes one snapshot message every ~0.5 s wall time plus discrete decision messages:
json
{ "type": "snapshot", "sim_time": 1234.0,
  "units": [{"id":"A1","kind":"ambulance","status":"en_route","lat":0,"lon":0,"incident_id":"I7"}],
  "incidents": [{"id":"I7","type":"accident","severity":3,"lat":0,"lon":0,"status":"dispatched"}],
  "hospitals": [{"id":"H1","beds_free":12,"icu_free":3}],
  "traffic": [{"id":"e12","coords":[[0,0],[0,0]],"congestion":0.6}],
  "metrics": {"avg_response_s": 0, "utilization": {"ambulance":0.4,"fire":0.2,"police":0.3}, "queued": 0} }
json
{ "type": "decision", "sim_time": 1234.0, "incident_id": "I7", "unit_id": "A2",
  "eta_s": 288, "explanation": "..." }
CORS for the frontend dev origin. Strategy names are looked up in a registry so future strategies (hungarian, mappo) can be added without touching the API.

Verify: httpx + WebSocket tests using the in-memory bus — start a run, receive snapshots, receive at least one decision, pause/stop work.

PHASE 6 — Dashboard (React + TS + Vite + Tailwind + MapLibre + Recharts)

Single-page dark command-center layout:

Map (MapLibre, OSM raster tiles, no token): station and hospital markers, live unit markers coloured by kind and styled by status, incident markers coloured by severity (pulse while unresolved), congestion overlay on road edges (green → red).
Control bar: Start / Pause / Resume / Stop / Reset, seed input, incident-rate slider, speed selector (1×, 5×, 20×), sim clock.
Agent panel: four cards (Ambulance, Fire, Police, Hospital) with idle / busy counts (hospital: beds and ICU free), and the last action each agent took.
Incident list: active incidents with type, severity, status and elapsed time.
Decision log: scrolling list of decisions; clicking one opens the full explanation with the candidates table (unit, ETA, distance, chosen ✓).
Metrics: Recharts line chart of rolling average response time by incident type, bar chart of utilisation by unit kind, KPI tiles (avg response, queued, traffic delay).
useRunSocket hook with auto-reconnect; types.ts mirrors the backend snapshot exactly; loading and error states; works at 1280 px and above.

Verify: npm run build and npm run lint pass; a small vitest test for the reducer that applies snapshots and decisions to state; manual demo via make demo.

PHASE 7 — Experiments, docs, polish
backend/experiments/run_experiment.py: CLI --strategy nearest --episodes 20 --seeds 1-20 --duration 3600 --rate 90 --out results/nearest.csv. Headless (InMemoryBus, no DB unless --persist). CSV columns: strategy, seed, incidents, avg_response_s, p95_response_s, ambulance_util, fire_util, police_util, mean_traffic_delay_s, queued_end. Also print a summary table. The output schema must be reusable for Hungarian/MAPPO later.
README.md: overview, architecture diagram (Mermaid), quick start (no-Docker and Docker), scenario config, how to add a strategy, how to run experiments, the Stage 2/3 roadmap.
docs/ARCHITECTURE.md: event flow for one accident incident, step by step.
make demo starts the backend and frontend and opens the dashboard.

Verify: make experiment produces a CSV; the 20-episode run finishes in under ~2 minutes on a laptop.

VERIFICATION COMMANDS (put in AGENTS.md)
make install
make lint
make test            # backend pytest + frontend vitest
make experiment      # baseline CSV
make demo            # live dashboard
docker compose up --build
DEFINITION OF DONE
make test and make lint pass on a clean checkout with no SUMO, Redis, Postgres or internet.
make demo shows a live map with units moving, incidents appearing, decisions with explanations, and metrics updating.
Same seed ⇒ identical experiment CSV rows.
docker compose up --build brings up Redis + Postgres/PostGIS + backend + frontend, and the dashboard works with BUS=redis.
Adding a new strategy requires only a new file in strategies/ and one registry line.
docs/DECISIONS.md lists every assumption you made.
FINAL REPORT

When finished, print: what was built per phase, how to run it, test results, what is skipped or best-effort (e.g. SUMO backend status), and a short list of the exact next steps for Stage 2 (Hungarian assignment + A* routing) and Stage 3 (PettingZoo env + MAPPO).

Content

PDF

PDF