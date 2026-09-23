# Decisions

- Treat the opened workspace as the repository root because it was empty and no nested repository existed.
- Use a deterministic networkx grid and SQLite by default so a full episode needs no services.
- Keep live simulation/API mechanics intentionally small for Stage 1; Redis and SUMO integrations are opt-in adapters.
- GridSim dashboards use only a vector-rendered grid on a light surface; no real-world tiles are loaded over synthetic coordinates.
- On hosts without GNU Make, invoke equivalent commands from `Makefile` directly (documented in README).
- Store persisted payloads as JSON text for the initial SQLite/Postgres schema so Stage 2 can evolve the schema without coupling the simulation to an ORM.
- Use incident arrival interval seconds for the experiment CLI `--rate`, matching the task's example value of 90 seconds; API/scenario rates are incidents per minute.
- The current SUMO class is a guarded adapter boundary requiring TraCI and inherits grid behavior until a SUMO network/config is available; it is best-effort and is not a TraCI runtime implementation yet.
- Redis Streams provides XADD/groups/ack transport, while live API runs use the manager's agent instances rather than separate background Redis worker processes.
- Hospital beds/ICU capacity are reserved during injured-patient transport and released after a fixed five-minute stay; no clinical queue policy is modeled.

## UI Fix

- Root cause: the browser always loaded OSM raster tiles while rendering a synthetic GridSim graph and used MapLibre marker wrappers, creating a street mismatch and default icon clutter; dark CSS and glow styling also contradicted the light UI intent.
- GridSim now renders roads, intersections, and plain entity shapes as SVG on light design tokens. A startup guard rejects tile URLs in GridSim mode, and `scripts/check_design.py` checks surfaces, effects, neon colors, and map imports. SUMO/TraCI is still a stub here, so there is no active real-map tile mode yet.
- Assumption: use one muted blue accent for all entities; distinguish entity types by shape only.

## Stage 2

- A* uses Manhattan distance times the free-flow minimum edge time as an admissible heuristic. Congestion scales edge times; emergency response uses 1.3× speed and a further 1.2× while a police corridor is cleared. Measured full-grid route: 0.44 ms for a 15-node path across 3.5 km (comfortably below the 50 ms target; hardware and load affect the number).
- Hungarian assignment minimizes `route_eta × capacity_factor × corridor_factor`. `capacity_factor` is 1.5 for ambulance demand at severity 3+ when total free ICU beds are zero, otherwise 1. `corridor_factor` is 0.95 for police when any corridor is actively cleared, otherwise 1. Candidate choices retain ETA and distance explanations and call out a local-nearest trade-off. These simple weights are assumptions for simulation comparison, not calibrated operational policy.
- Nearest remains the default. A tick's pending incidents are grouped by responder kind and assigned together; same-tick scenario pairing uses identical integer seeds for each strategy. Comparison defaults to seeds 1..N and reports mean, median, and standard deviation.
- Smoke comparison (seeds 1–2, 600 simulated seconds, 90-second mean incident interval) produced matching aggregate nearest/Hungarian metrics; with these low simultaneous-demand scenarios the optimization had no measured improvement. The runner still writes the observed improvement percentage instead of promising a gain.
- SUMO/TraCI remains a GridSim fallback because the adapter is not a real TraCI runtime; no real-map tile mode is exposed.

## Live City Map Fix

- Diagnosis from the seed 1 WebSocket snapshot: a road edge and node are `edge={"id":"0_0-1_0","from_node":"n_0_0","to_node":"n_1_0","x1":0.0,"y1":0.0,"x2":0.0,"y2":1.0,"congestion":0.7839923079463914}` and `node={"id":"n_0_0","x":0.0,"y":0.0}`. The backend grid values and endpoint identities are correct. Causes (a)–(d) do not apply to the failure.
- Root cause: the SVG renderer spread a `{x,y}` point onto `<line>`, whose endpoints are named `x1,y1,x2,y2`; omitted SVG line attributes defaulted to zero, so all roads originated at `(0,0)`. The previous renderer also used fixed 1000×650 dimensions and an uneven geographic projection.
- Fix: WebSocket snapshots now include Pydantic-validated grid-unit nodes and edges with explicit endpoints. The SVG reads those endpoints, computes one aspect-preserving scale from node bounds, measures its container with `ResizeObserver`, and uses the same grid transform for entity markers. Invalid records are skipped with one console error per id. CSS gives cards and toolbar children shrinkable widths, wraps controls, and provides a 200px Strategy selector.
- Assumption: geographic markers are rounded to the nearest in-bounds GridSim intersection, matching `GridSim._node`, so units and incidents remain aligned to the synthetic street network.
- Playwright verified no horizontal overflow at 1280×800 and 1920×1080 and saved the visual baseline at `docs/screenshots/map-fixed.png`.
