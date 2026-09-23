import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  reporter: 'list',
  use: { ...devices['Desktop Chrome'], baseURL: 'http://127.0.0.1:5173', headless: true },
  webServer: [
    { command: 'python -m uvicorn app.main:app --host 127.0.0.1 --port 8000', cwd: '../backend', url: 'http://127.0.0.1:8000/health', reuseExistingServer: true, timeout: 30000 },
    { command: 'npm run dev -- --host 0.0.0.0', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 30000 },
  ],
});
