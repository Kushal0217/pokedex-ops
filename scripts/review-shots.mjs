// Dev tooling: captures the review screenshots and checks layout rules against a running preview.
// Usage: npm run build && npm run preview   (in one terminal)
//        node scripts/review-shots.mjs [url] [outDir] [scale]
// Needs Playwright available to Node (it is not a site dependency).
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const url = process.argv[2] ?? 'http://localhost:4173/';
const outDir = process.argv[3] ?? 'review';
const scale = Number(process.argv[4] ?? 2);
mkdirSync(outDir, { recursive: true });

const viewports = { desktop: { width: 1280, height: 800 }, phone: { width: 390, height: 844 }, narrow: { width: 320, height: 640 } };
const modes = ['Day', 'Evening', 'Night'];
const failures = [];

const browser = await chromium.launch();
for (const [name, viewport] of Object.entries(viewports)) {
  const context = await browser.newContext({ viewport, deviceScaleFactor: scale, hasTouch: name !== 'desktop' });
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  for (const mode of modes) {
    await page.getByRole('radio', { name: mode }).check({ force: true });
    await page.waitForTimeout(500);
    const resolved = await page.evaluate(() => document.documentElement.dataset.time);
    if (resolved !== mode.toLowerCase()) failures.push(`${name}/${mode}: data-time is ${resolved}`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 0) failures.push(`${name}/${mode}: horizontal overflow of ${overflow}px`);
    for (const text of ['Kushal Gaddam', 'Menu', 'Kasama', 'Chicago', 'Ramen shop']) {
      if (!(await page.getByText(text, { exact: false }).first().isVisible())) failures.push(`${name}/${mode}: "${text}" not visible`);
    }
    if (name !== 'narrow') await page.screenshot({ path: `${outDir}/${name}-${mode.toLowerCase()}.png`, fullPage: true });
  }
  // The menu closes and reopens from real controls (mouse/keyboard).
  await page.getByRole('button', { name: 'Close menu' }).click();
  if (await page.getByRole('heading', { name: 'Menu' }).count()) failures.push(`${name}: menu did not close`);
  await page.getByRole('button', { name: /Ramen shop/ }).focus();
  await page.keyboard.press('Enter');
  if (!(await page.getByRole('heading', { name: 'Menu' }).isVisible())) failures.push(`${name}: menu did not reopen by keyboard`);
  await context.close();
}
await browser.close();

if (failures.length) {
  console.error('FAILED\n' + failures.join('\n'));
  process.exit(1);
}
console.log(`OK: ${Object.keys(viewports).length} viewports x ${modes.length} modes, no overflow, text visible, menu toggles. Screenshots in ${outDir}/`);
