import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: 'pune.spec.ts',
  fullyParallel: false,
  reporter: 'list',
  timeout: 90000,
  projects: [{ name: 'pune', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
  use: { baseURL: 'http://127.0.0.1:5373', headless: true },
  webServer: [
    { command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8200', cwd: '../backend', url: 'http://127.0.0.1:8200/health', reuseExistingServer: false, timeout: 30000, env: { SIMULATION_MODE: 'pune' } },
    { command: 'npm run dev -- --host 0.0.0.0 --port 5373', url: 'http://127.0.0.1:5373', reuseExistingServer: false, timeout: 30000, env: { VITE_SIMULATION_MODE: 'pune', VITE_BASEMAP: 'carto-light', VITE_EXPOSE_MAP: '1', API_PROXY_TARGET: 'http://127.0.0.1:8200' } },
  ],
});
