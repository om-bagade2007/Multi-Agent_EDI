import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

test.beforeEach(async ({ request }) => {
  const scenario = await request.get('http://127.0.0.1:8200/scenario');
  expect(scenario.ok()).toBeTruthy();
  expect((await scenario.json()).mode).toBe('pune');
});

test('Pune map loads facilities, roads and live response markers without overflow or console errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/cartocdn.com/**', route => route.abort());
  await page.goto('/');
  await expect(page).toHaveTitle(/Pune/);
  await expect(page.getByRole('heading', { name: 'Pune Emergency Response Simulation' })).toBeVisible();
  const canvas = page.locator('.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(async () => (await canvas.boundingBox())?.width ?? 0).toBeGreaterThan(600);
  await expect.poll(async () => (await canvas.boundingBox())?.height ?? 0).toBeGreaterThan(400);
  await expect(page.locator('.facility-marker')).toHaveCount(19);
  const screenshotDir = resolve(process.cwd(), '../docs/screenshots');
  await mkdir(screenshotDir, { recursive: true });
  await page.screenshot({ path: resolve(screenshotDir, 'pune-map.png'), fullPage: true });
  await expect(page.getByText(/GridSim|\bgrid\b/i)).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.getByLabel('Speed').selectOption('10');
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect(page.locator('.pune-map')).toHaveAttribute('data-roads-ready', 'true');
  await expect(page.locator('.unit-marker')).not.toHaveCount(0, { timeout: 20000 });
  await expect(page.locator('.incident-marker')).not.toHaveCount(0, { timeout: 20000 });
  const markerSizes = await page.locator('.pune-marker').evaluateAll(items => items.map(item => {
    const box = item.getBoundingClientRect();
    return Math.max(box.width, box.height);
  }));
  expect(Math.max(...markerSizes, 0)).toBeLessThanOrEqual(40);
  await page.screenshot({ path: resolve(screenshotDir, 'pune-running.png'), fullPage: true });
  await page.waitForTimeout(60000);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
