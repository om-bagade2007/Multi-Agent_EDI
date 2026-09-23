import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'grid.spec.ts',
  fullyParallel: false,
  reporter: 'list',
  projects: [{ name: 'gridsim-dev', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
  use: { baseURL: 'http://127.0.0.1:5273', headless: true },
  webServer: [
    { command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8100', cwd: '../backend', url: 'http://127.0.0.1:8100/health', reuseExistingServer: false, timeout: 30000, env: { SIMULATION_MODE: 'gridsim' } },
    { command: 'npm run dev -- --host 0.0.0.0 --port 5273', url: 'http://127.0.0.1:5273', reuseExistingServer: false, timeout: 30000, env: { SIMULATION_MODE: 'gridsim', VITE_SIMULATION_MODE: 'gridsim', API_PROXY_TARGET: 'http://127.0.0.1:8100' } },
  ],
});
