import { expect, test } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';

test('map grid fits the dashboard at desktop widths', async ({ page }) => {
  await page.setViewportSize({ width: 775, height: 900 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Emergency Response Simulation' })).toBeVisible();
  await expect(page.getByLabel('Strategy')).toContainText('Nearest resource');
  await expect(page.locator('.grid-map line')).toHaveCount(112, { timeout: 10000 });
  expect(await page.locator('.grid-map line').count()).toBeGreaterThan(0);
  const oversizedMarkers = await page.locator('.map-marker').evaluateAll(items => items.filter(item => {
    const box = item.getBoundingClientRect();
    return box.width > 40 || box.height > 40;
  }).length);
  expect(oversizedMarkers).toBe(0);
  const overflow775 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(overflow775).toBe(true);
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(page.locator('.grid-map line')).toHaveCount(112, { timeout: 10000 });
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect(page.locator('.grid-map line')).toHaveCount(112, { timeout: 20000 });
  const box = await page.locator('.map').boundingBox();
  expect(box!.width).toBeGreaterThan(700);
  const sizes = await page.locator('.map-marker').evaluateAll(els => els.map(element => {
    const rect = element.getBoundingClientRect();
    return Math.max(rect.width, rect.height);
  }));
  expect(Math.max(...sizes, 0)).toBeLessThanOrEqual(40);
  const overflow1280 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(overflow1280).toBe(true);
  const screenshotPath = resolve(process.cwd(), '../docs/screenshots/map-fixed.png');
  await mkdir(resolve(screenshotPath, '..'), { recursive: true });
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await page.setViewportSize({ width: 1920, height: 1080 });
  const overflow1920 = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth);
  expect(overflow1920).toBe(true);
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
});
