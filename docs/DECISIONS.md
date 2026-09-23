# Decisions

- Treat the opened workspace as the repository root because it was empty and no nested repository existed.
- Use a deterministic networkx grid and SQLite by default so a full episode needs no services.
- Keep live simulation/API mechanics intentionally small for Stage 1; Redis and SUMO integrations are opt-in adapters.
- Use OSM raster tiles in the browser for the map; internet access is only needed to display those tiles.
- On hosts without GNU Make, invoke equivalent commands from `Makefile` directly (documented in README).
