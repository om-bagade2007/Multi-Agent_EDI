# Project operating rules

- Use Python 3.11+, Pydantic v2, type hints, ruff and pytest; use strict TypeScript.
- All run randomness must come from the explicitly passed `numpy.random.Generator`.
- Defaults are GridSim, in-memory event bus and SQLite; SUMO, Redis and Postgres are optional.
- Keep modules focused and near or below 300 lines. Document public APIs.
- Record assumptions in `docs/DECISIONS.md`.
- Out-of-scope strategy and RL work stays at documented Protocol/interface level.
- Work by phase, verify before committing with `git commit -m "phase N: <summary>"`.

## Verification commands

```text
make install
make lint
make test            # backend pytest + frontend vitest
make experiment      # baseline CSV
make demo            # live dashboard
docker compose up --build
```
