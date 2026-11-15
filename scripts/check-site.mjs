// Dev tooling: behaviour checks and review screenshots against a running preview.
// Usage: npm run build && npm run preview   (in one terminal)
//        node scripts/check-site.mjs [url] [outDir] [scale]
// Needs Playwright available to Node (it is not a site dependency).
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const url = process.argv[2] ?? 'http://localhost:4173/';
const outDir = process.argv[3] ?? 'review';
const scale = Number(process.argv[4] ?? 2);
mkdirSync(outDir, { recursive: true });

const failures = [];
let checks = 0;
const check = (ok, message) => { checks += 1; if (!ok) failures.push(message); };
const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const focusedText = (page) => page.evaluate(() => document.activeElement?.textContent?.trim() ?? '');
const overflow = (page) => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
const avatarPos = (page) => page.evaluate(() => { const s = document.querySelector('.avatar').style; return { left: parseFloat(s.left), top: parseFloat(s.top) }; });
const dialogs = (page) => page.getByRole('dialog').count();

const browser = await chromium.launch();

async function run(name, contextOptions, { shots = false } = {}) {
  const context = await browser.newContext({ deviceScaleFactor: scale, ...contextOptions });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  await page.goto(url, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const shot = async (label) => shots && page.screenshot({ path: `${outDir}/${name}-${label}.png` });

  // First screen: identity, explore cue, facts action.
  for (const text of ['Kushal Gaddam', 'Software Engineer', 'Explore.', 'Just the facts', 'Ramen shop']) {
    check(await page.getByText(text).first().isVisible(), `${name}: "${text}" not visible on first screen`);
  }
  check((await overflow(page)) <= 0, `${name}: horizontal overflow on the map`);

  // Lighting modes stay readable and overflow-free.
  for (const mode of ['Evening', 'Night', 'Day']) {
    await page.getByRole('radio', { name: mode }).check({ force: true });
    await page.waitForTimeout(400);
    check((await page.evaluate(() => document.documentElement.dataset.time)) === mode.toLowerCase(), `${name}: ${mode} not applied`);
    await shot(`map-${mode.toLowerCase()}`);
  }

  // Scroll the map a little (where the page is tall enough) so we can prove the position survives.
  await page.evaluate(() => window.scrollTo(0, 120));
  const place = page.getByRole('button', { name: /Ramen shop/ });
  await place.scrollIntoViewIfNeeded();
  const scrollBefore = await page.evaluate(() => window.scrollY);

  // Enter the shop from its labelled control.
  if (contextOptions.hasTouch) await place.tap(); else await place.click();
  const interior = page.getByRole('dialog', { name: 'Ramen shop' });
  check(await interior.isVisible(), `${name}: interior did not open`);
  check((await overflow(page)) <= 0, `${name}: horizontal overflow with interior open`);
  await page.waitForTimeout(350);
  await shot('interior');

  // Background is not interactive under the modal.
  check(await page.evaluate(() => { return !!document.querySelector('main').closest('[aria-hidden="true"], [inert]'); }), `${name}: map not hidden from assistive tech under modal`);
  const hit = await page.evaluate(() => { const b = document.querySelector('.facts-button').getBoundingClientRect(); const el = document.elementFromPoint(b.left + 5, b.top + 5); return !!el?.closest('.facts-button'); });
  check(!hit, `${name}: header button still clickable under modal`);

  // Open the menu; all favourites readable.
  const menuButton = page.getByRole('button', { name: /^Menu/ });
  if (contextOptions.hasTouch) await menuButton.tap(); else { await menuButton.focus(); await page.keyboard.press('Enter'); }
  const menu = page.getByRole('dialog', { name: 'Menu' });
  check(await menu.isVisible(), `${name}: menu did not open`);
  check(await menu.getByText('Kasama').isVisible() && await menu.getByText('Chicago').isVisible(), `${name}: Kasama / Chicago not readable`);
  check((await menu.getByText(/rating|updated/i).count()) === 0, `${name}: menu shows a rating or update date`);
  await page.waitForTimeout(350);
  await shot('menu');

  // Facts stay reachable from inside a scene, and focus comes back to where it was launched.
  await menu.getByRole('button', { name: 'Just the facts' }).click();
  const factsDialog = page.getByRole('dialog', { name: 'Just the facts' });
  check(await factsDialog.isVisible(), `${name}: facts did not open over the menu`);
  // Wait until the view has taken focus, as a person would before pressing a key.
  await page.waitForFunction(() => document.activeElement?.closest('[role="dialog"]')?.querySelector('h2')?.textContent === 'Just the facts');
  await page.keyboard.press('Escape');
  check(!(await factsDialog.isVisible()) && (await menu.isVisible()), `${name}: Escape on facts should close only facts`);
  check((await focusedText(page)) === 'Just the facts', `${name}: focus not returned to the facts launcher in the menu`);

  // Tab stays inside the top dialog.
  for (let i = 0; i < 8; i += 1) await page.keyboard.press('Tab');
  check(await page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]')), `${name}: Tab escaped the dialog`);

  // Escape closes the menu only; focus returns to the menu board.
  await page.keyboard.press('Escape');
  check(!(await menu.isVisible()) && (await interior.isVisible()), `${name}: Escape should close the menu and keep the interior`);
  check((await focusedText(page)).startsWith('Menu'), `${name}: focus not returned to the menu board (got "${await focusedText(page)}")`);

  // Escape again returns to the map: focus on the place control, scroll position kept.
  await page.keyboard.press('Escape');
  await page.waitForTimeout(100);
  check((await dialogs(page)) === 0, `${name}: interior did not close`);
  check((await focusedText(page)).startsWith('Ramen shop'), `${name}: focus not returned to the place control (got "${await focusedText(page)}")`);
  check((await page.evaluate(() => window.scrollY)) === scrollBefore, `${name}: map scroll position changed (${scrollBefore} -> ${await page.evaluate(() => window.scrollY)})`);
  check(await page.evaluate(() => !document.querySelector('main').closest('[aria-hidden="true"], [inert]')), `${name}: map left hidden after closing`);

  // Visible close controls work too.
  await place.click();
  await page.getByRole('button', { name: 'Back to town' }).click();
  check((await dialogs(page)) === 0, `${name}: "Back to town" did not close the interior`);

  // Just the facts: resume and contact actions.
  await page.getByRole('button', { name: /Just the facts/ }).click();
  check(await factsDialog.isVisible(), `${name}: facts did not open from the header`);
  const hrefs = await factsDialog.getByRole('link').evaluateAll((links) => links.map((a) => a.getAttribute('href')));
  for (const expected of ['resume.pdf', 'mailto:Kushalgaddam171@gmail.com', 'tel:+18505185547', 'https://www.linkedin.com/in/kg15', 'https://github.com/Kushal0217']) {
    check(hrefs.includes(expected), `${name}: facts link missing: ${expected}`);
  }
  check((await factsDialog.getByRole('link', { name: /Download resume/ }).getAttribute('download')) !== null, `${name}: resume link is not a download`);
  const resume = await page.request.get(new URL('resume.pdf', url).href);
  check(resume.ok() && sha(await resume.body()) === sha(readFileSync('source-assets/resume.pdf')), `${name}: served resume.pdf is not the selected resume, byte for byte`);
  check((await overflow(page)) <= 0, `${name}: horizontal overflow with facts open`);
  await page.waitForTimeout(350);
  await shot('facts');
  await page.getByRole('button', { name: 'Close' }).click();
  check((await focusedText(page)).startsWith('Just the facts'), `${name}: focus not returned to the header facts button`);

  // Optional walking.
  await page.evaluate(() => window.scrollTo(0, 0));
  if (!contextOptions.hasTouch) {
    const start = await avatarPos(page);
    await page.keyboard.down('d'); await page.waitForTimeout(400); await page.keyboard.up('d');
    const afterD = await avatarPos(page);
    check(afterD.left > start.left + 2, `${name}: W A S D did not move the avatar`);
    // Arrow keys outside the scene must not steer (they belong to the page / radios).
    await page.getByRole('button', { name: /Just the facts/ }).focus();
    await page.keyboard.down('ArrowLeft'); await page.waitForTimeout(250); await page.keyboard.up('ArrowLeft');
    check(Math.abs((await avatarPos(page)).left - afterD.left) < 0.01, `${name}: arrow keys steered the avatar while focus was outside the map`);
    await page.getByRole('group', { name: /Town map/ }).focus();
    await page.keyboard.down('ArrowLeft'); await page.waitForTimeout(250); await page.keyboard.up('ArrowLeft');
    check((await avatarPos(page)).left < afterD.left - 1, `${name}: arrow keys did not move the avatar with the map focused`);
    // A held key must stop on window blur (no runaway avatar).
    await page.keyboard.down('d'); await page.waitForTimeout(100);
    await page.evaluate(() => window.dispatchEvent(new Event('blur')));
    await page.waitForTimeout(150); const p1 = await avatarPos(page); await page.waitForTimeout(200); const p2 = await avatarPos(page);
    await page.keyboard.up('d');
    check(Math.abs(p1.left - p2.left) < 0.01, `${name}: avatar kept walking after the window lost focus`);
    // Walls stop the avatar: it cannot leave the scene.
    await page.keyboard.down('a'); await page.waitForTimeout(2600); await page.keyboard.up('a');
    check((await avatarPos(page)).left >= -2, `${name}: avatar walked out of the scene`);
  }
  // Tap / click the ground: the avatar walks there.
  await page.evaluate(() => document.querySelector('.scene').scrollIntoView({ block: 'end' }));
  const box = await page.locator('.scene').boundingBox();
  const before = await avatarPos(page);
  const ground = { x: box.x + box.width * 0.86, y: box.y + box.height * 0.84 };
  if (contextOptions.hasTouch) await page.touchscreen.tap(ground.x, ground.y); else await page.mouse.click(ground.x, ground.y);
  await page.waitForFunction(() => parseFloat(document.querySelector('.avatar').style.left) > 70, null, { timeout: 12000 }).catch(() => {});
  const walked = await avatarPos(page);
  check(Math.abs(walked.left - before.left) > 5 && walked.left > 70, `${name}: tapping the ground did not move the avatar there`);
  check((await dialogs(page)) === 0, `${name}: tapping the ground opened a dialog`);
  // Tap / click the shop itself: opens at once.
  const shop = { x: box.x + box.width * 0.5, y: box.y + box.height * 0.5 };
  if (contextOptions.hasTouch) await page.touchscreen.tap(shop.x, shop.y); else await page.mouse.click(shop.x, shop.y);
  check(await interior.isVisible(), `${name}: selecting the shop building did not open it promptly`);
  await page.keyboard.press('Escape');
  if (!contextOptions.hasTouch) {
    // Walking up into the doorway enters the shop.
    await page.keyboard.down('w'); await page.waitForTimeout(900); await page.keyboard.up('w');
    check(await interior.isVisible(), `${name}: walking into the doorway did not enter the shop`);
    await page.keyboard.press('Escape');
    await page.keyboard.down('w'); await page.waitForTimeout(100); await page.keyboard.up('w');
  }
  check(errors.length === 0, `${name}: console errors: ${errors.join(' | ')}`);
  await context.close();
}

await run('desktop', { viewport: { width: 1280, height: 800 } }, { shots: true });
await run('phone', { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true }, { shots: true });
await run('narrow', { viewport: { width: 320, height: 568 }, hasTouch: true, isMobile: true });
await run('reduced-motion', { viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
await run('short-desktop', { viewport: { width: 1024, height: 520 } });

// A direct #facts link opens the plain view.
{
  const page = await browser.newPage();
  await page.goto(url + '#facts', { waitUntil: 'networkidle' });
  check(await page.getByRole('dialog', { name: 'Just the facts' }).isVisible(), 'direct #facts link did not open the facts view');
  await page.close();
}
await browser.close();

if (failures.length) {
  console.error(`FAILED (${failures.length} of ${checks} checks)\n` + failures.join('\n'));
  process.exit(1);
}
console.log(`OK: ${checks} checks passed across desktop, phone, narrow phone, reduced motion and short desktop. Screenshots in ${outDir}/`);
