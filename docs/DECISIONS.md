# Decisions

- Treat the opened workspace as the repository root because it was empty and no nested repository existed.
- Use a deterministic networkx grid and SQLite by default so a full episode needs no services.
- Keep live simulation/API mechanics intentionally small for Stage 1; Redis and SUMO integrations are opt-in adapters.
- Use OSM raster tiles in the browser for the map; internet access is only needed to display those tiles.
- On hosts without GNU Make, invoke equivalent commands from `Makefile` directly (documented in README).
- Store persisted payloads as JSON text for the initial SQLite/Postgres schema so Stage 2 can evolve the schema without coupling the simulation to an ORM.
- Use incident arrival interval seconds for the experiment CLI `--rate`, matching the task's example value of 90 seconds; API/scenario rates are incidents per minute.
- The current SUMO class is a guarded adapter boundary requiring TraCI and inherits grid behavior until a SUMO network/config is available; it is best-effort and is not a TraCI runtime implementation yet.
- Redis Streams provides XADD/groups/ack transport, while live API runs use the manager's agent instances rather than separate background Redis worker processes.
- Hospital beds/ICU capacity are reserved during injured-patient transport and released after a fixed five-minute stay; no clinical queue policy is modeled.
