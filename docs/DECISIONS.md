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

## Startup Map Visibility

- The initial blank map had two causes: the dashboard only received a road network in the active-run WebSocket, and `GridMap` returned empty geometry whenever its simulation snapshot was null—even if the static road network had loaded. A new `/scenario/network` endpoint supplies the default grid on page load, and the renderer now uses that network until a live snapshot replaces it.
- MapLibre is not used for the default GridSim view because it models a synthetic grid, not real geographic streets. A real-city basemap should only be enabled with a real, aligned SUMO/OSM network.

## Fixed GridMap Scaling and Layout

- Root cause of the giant map markers: the SVG `viewBox` depended on a `ResizeObserver` measurement that could initially be zero or very small. That made marker radii and labels appear greatly enlarged. The page also lacked a doctype, so browsers could use quirks mode; the square aspect ratio and 70vh maximum height kept the map card narrow inside its wider grid column. Vite's React plugin was configured as `react` rather than invoked as `react()`.
- Decision: use a fixed 1000-by-1000 logical SVG coordinate space, fit grid bounds into it with 60 units of padding, and size roads, nodes, markers, and labels in that same space. Keep the map classes used by end-to-end checks and disable text selection inside the map.
- Layout decision: let the map card fill its grid column, give the map canvas the remaining card height, and preserve the SVG aspect ratio within that canvas. The document uses standards mode through an explicit HTML doctype.

## Pune-Only Demo Build

- Diagnosis: the repository initially defaulted to GridSim even though an OSM network builder and Pune simulation classes were being added. The API and UI mode were not synchronized, the frontend bundled the GridMap import into its main render path, the local server commands did not pin/verify Pune mode, and no portable committed Pune network artifacts existed at the start of this implementation. Root-relative `PUNE_DATA_DIR` is now resolved from `backend/app/config.py`, independent of the process working directory.
- Pune is now the backend and public dashboard default. `GET /scenario` is the UI's mode source of truth. Missing or invalid Pune data returns an explicit health error and HTTP 503 for network/facility endpoints; the UI surfaces the server detail and does not substitute GridSim. The GridMap source and its tests live in `frontend/src/dev/`; the component is lazy-loaded only for the developer-only backend mode.
- Dataset contract: central Pune bbox is south 18.47, north 18.58, west 73.79, east 73.93; network generation uses OSM motorways, trunk, primary, secondary, tertiary and their links, retains the largest strongly connected component, and serializes 5,790 nodes and 9,681 directed edges. The simplified cached roads GeoJSON is about 2.22 MB; network JSON about 3.03 MB; test fixture about 5 KB. Data files stay below the 10 MB distribution limit. All facility locations are snapped within 300 m. Current OSM facilities include 10 hospitals, 6 fire stations, and 0 successful police results; three police simulation facilities were therefore added at Shivajinagar, Deccan, and Swargate (each under 100 m snap distance). Synthetic hospital and fire locations are allowed only if OSM returns fewer than their documented minimums; current data did not require those additions.
- OpenStreetMap attribution is retained. The builder attempts the primary Overpass endpoint and two mirrors, then uses only its compressed cached OSM graph. It never fabricates road geometry. `make pune-data` validates existing committed outputs; `--force` requests a fresh rebuild. Facilities may use disclosed synthetic Pune landmarks only to meet minimum simulation coverage after OSM query failures.
- Routing uses A* with congestion-scaled edge travel times, haversine distance divided by maximum speed as the heuristic, and a bounded 30,000-entry per-simulation cache keyed by origin, destination, hour, emergency, and corridor state. Edge noise and incident selection use the seeded NumPy generator. Peak-hour road-class multipliers, emergency speed modifiers, 15-bed / 4-ICU per-hospital capacity, and five-minute simulated hospital stays are explicit simulation assumptions, not calibrated operational data.
- CARTO light tiles are an optional context layer. Pune roads are an independent GeoJSON layer and remain visible with `VITE_BASEMAP=none` or when tile requests fail. Markers use small CSS HTML elements; dynamic coordinates are finite and bbox-validated before sending/rendering. Rotation is disabled, map bounds stay around Pune, and facilities render before a run.
- Local visual check of CARTO's previously configured public tile URL returned repeated `API KEY REQUIRED` tiles. To keep the default demo clean and offline-capable, `VITE_BASEMAP=none` is the default in the checked-in example, local demo, and Docker build; `VITE_BASEMAP=carto-light` remains an explicit opt-in and failed requests cannot cover the independent road layer. Attribution is displayed once in the map card.
- A live-motion review found that a unit's first route previously used the graph's first node because the simulation had no pre-dispatch location registry. PuneSim now registers each unit's snapped station position at manager setup, so initial routes begin from the actual facility location. A completed run marks its WebSocket as terminal to avoid futile reconnect retries after the server closes the stream.
- Demo readiness uses isolated Playwright service ports and `reuseExistingServer: false`; Pune is the default E2E suite and GridSim checks run separately with `npm run test:e2e:grid`. `make doctor` reports mode, data, counts, and port state. The paired Pune comparison writes stable paths under root `results/` so the existing dashboard comparison endpoint can read the same latest-result file.
- The local machine had an older GridSim backend already answering on 8000, so Pune Playwright uses its own isolated 8200/5373 ports with server reuse disabled; the developer GridSim suite independently uses 8100/5273. Normal demo instructions continue to use 8000/5173 on a clean host.
