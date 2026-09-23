# Landing Page Plan

## Goal

Give first-time visitors a clear introduction to the urban emergency-response simulator, explain what the simulation demonstrates, and guide them into the interactive dashboard or setup instructions. Keep the existing dashboard as the working application; this plan does not redesign it.

## Audience and primary actions

- **Students and researchers:** understand the simulation and open the dashboard to run a scenario.
- **Developers/evaluators:** see the architecture, supported dispatch strategies, and reproducible experiment workflow.
- Primary action: **Open the simulation**.
- Secondary action: **How to run locally**.

## Page outline

1. **Header:** project name, concise links to Simulation, How it works, Experiments, and Documentation; one prominent “Open simulation” button.
2. **Hero:** plain title such as “Explore urban emergency response”; one sentence describing seeded GridSim scenarios and dispatch comparison; a real screenshot of the light dashboard; primary and secondary actions.
3. **At-a-glance facts:** deterministic grid, three response services, A* routing, and nearest/Hungarian dispatch. Use text and restrained layout, no decorative icon set.
4. **How it works:** a short flow from incident generation, through routing and dispatch, to response metrics.
5. **Try the simulation:** explain selecting a seed, incident rate, speed, and strategy, then starting and comparing a run. Link directly to the dashboard.
6. **Experiments:** summarize paired-seed comparison output and link to command examples and result files.
7. **Run locally:** show Python/Node prerequisites and link to the platform-specific README instructions.
8. **Scope and limitations:** identify GridSim as synthetic, state that real SUMO/TraCI is not integrated yet, and list Stage 3 work as future scope.
9. **Footer:** repository, README, test instructions, and project status.

## Visual direction

- Reuse the existing light palette and muted blue accent from the dashboard.
- Use a full-width responsive layout with a readable text measure, consistent spacing, and real project imagery.
- Use CSS/vector diagrams for architecture. Do not add map tiles, glow, gradients, icon packs, or a dark theme.
- Keep the page usable on phone, tablet, and desktop, with keyboard focus, semantic headings, and accessible contrast.

## Implementation sequence

1. Confirm the repository URL, final project name, and the preferred primary action destination.
2. Build the static responsive page and reuse existing documentation and screenshot assets.
3. Add links to dashboard and local setup; verify paths work from both root and subpath hosting.
4. Check narrow and desktop widths, keyboard navigation, page overflow, and broken links.
5. Publish only after project owners choose the hosting target and provide the repository URL.

## Acceptance checks

- A first-time visitor can tell what the software simulates and that GridSim uses a synthetic road grid.
- The dashboard and local setup are reachable in one click from the landing page.
- No horizontal overflow or clipped content at mobile, 1280px, and 1920px widths.
- All actions have accessible names and visible keyboard focus.
