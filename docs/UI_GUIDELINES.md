# UI Guidelines

- Default to the light palette in `frontend/src/style.css`: near-white `--bg` and `--surface`, dark `--text`, muted gray, and one muted blue accent.
- Keep the heading and clock plain and static. Avoid shadows, glow, filters, animated emphasis, and neon colors.
- In GridSim mode, draw roads and intersections as vectors on a plain surface. Use circles for units, diamonds with a numeral for incidents, filled squares for stations, and outlined squares for hospitals.
- Keep charts, tables, controls, and result selectors dense and readable with the same tokens.
- Keep the next-run strategy selector plain and disabled during a live run; render experiment comparisons as a compact table with a text-only empty state.

## Known failure mode

The earlier dashboard placed a synthetic GridSim road grid and numbered markers over full-color OpenStreetMap tiles. GridSim coordinates do not describe those real streets, so the grid visibly cut across unrelated roads. The dark, glowing command-console styling and default map markers also violated this guide. GridSim must not initialize a tile source; use its vector graph on a light surface instead.
