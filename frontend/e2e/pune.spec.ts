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
  let blockedTileRequests = 0;
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*cartocdn.com/**', route => {
    blockedTileRequests += 1;
    return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/nmUAAAAASUVORK5CYII=', 'base64') });
  });
  await page.goto('/');
  await expect(page).toHaveTitle(/Pune/);
  await expect(page.getByRole('heading', { name: 'Pune Emergency Response Simulation' })).toBeVisible();
  const canvas = page.locator('.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  await expect.poll(async () => (await canvas.boundingBox())?.width ?? 0).toBeGreaterThan(600);
  await expect.poll(async () => (await canvas.boundingBox())?.height ?? 0).toBeGreaterThan(400);
  await expect(page.locator('.facility-marker')).toHaveCount(19);
  await expect.poll(() => blockedTileRequests).toBeGreaterThan(0);
  await expect(page.locator('.pune-map')).toHaveAttribute('data-roads-loaded', 'true', { timeout: 20000 });
  await expect(page.locator('.pune-map')).toHaveAttribute('data-roads-ready', 'true');
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
  await expect.poll(() => page.locator('.region-label:not(.region-hidden)').count()).toBeGreaterThanOrEqual(5);
  await page.getByLabel('Regions').uncheck();
  await expect(page.locator('.region-label:not(.region-hidden)')).toHaveCount(0);
  await page.getByLabel('Regions').check();
  const assertAnchors = async () => {
    const offsets = await page.evaluate(() => {
      const map = window.__puneMap!;
      const container = map.getContainer().getBoundingClientRect();
      return [...map.getContainer().querySelectorAll<HTMLElement>('.maplibregl-marker')].map(element => {
        const point = map.project((element as HTMLElement & { _lngLat: { lng: number; lat: number } })._lngLat as never);
        const box = element.getBoundingClientRect();
        return Math.hypot(box.left + box.width / 2 - container.left - point.x, box.top + box.height / 2 - container.top - point.y);
      });
    });
    expect(offsets.length).toBeGreaterThan(20);
    expect(Math.max(...offsets)).toBeLessThanOrEqual(2);
  };
  const waitForIdle = () => page.evaluate(() => new Promise<void>(resolve => window.__puneMap!.once('idle', resolve)));
  await assertAnchors();
  await page.evaluate(() => window.__puneMap!.setZoom(window.__puneMap!.getZoom() + 2)); await waitForIdle(); await assertAnchors();
  await page.screenshot({ path: resolve(screenshotDir, 'pune-zoomed-in.png'), fullPage: true });
  await page.evaluate(() => window.__puneMap!.setZoom(window.__puneMap!.getZoom() - 1)); await waitForIdle(); await assertAnchors();
  await page.evaluate(() => window.__puneMap!.panBy([200, 100], { duration: 0 })); await waitForIdle(); await assertAnchors();
  await page.screenshot({ path: resolve(screenshotDir, 'pune-zoomed-out.png'), fullPage: true });
  const roadHits = await page.evaluate(() => {
    const map = window.__puneMap!;
    return [...map.getContainer().querySelectorAll<HTMLElement>('.incident-marker')].map(element => {
      const marker = element.parentElement! as HTMLElement & { _lngLat: { lng: number; lat: number } };
      const point = map.project(marker._lngLat as never);
      return map.queryRenderedFeatures([[point.x - 6, point.y - 6], [point.x + 6, point.y + 6]], { layers: ['pune-roads'] }).length;
    });
  });
  expect(roadHits.length).toBeGreaterThan(0);
  expect(roadHits.every(count => count > 0)).toBe(true);
  await expect.poll(() => page.evaluate(() => window.__puneMap?.isSourceLoaded('carto-base') ?? false)).toBe(true);
  await page.screenshot({ path: resolve(screenshotDir, 'pune-basemap.png'), fullPage: true });
  await page.screenshot({ path: resolve(screenshotDir, 'pune-running.png'), fullPage: true });
  await page.waitForTimeout(60000);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('roads and facilities remain visible when CARTO tiles are blocked', async ({ page }) => {
  await page.route('**/*cartocdn.com/**', route => route.abort());
  await page.goto('/');
  await expect(page.locator('.pune-map')).toHaveAttribute('data-roads-ready', 'true');
  await expect(page.locator('.facility-marker')).toHaveCount(19);
  await expect(page.getByRole('status').getByText('Basemap unavailable. Showing roads only.')).toBeVisible({ timeout: 20000 });
});
