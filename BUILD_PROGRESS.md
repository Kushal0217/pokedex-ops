# Build progress

| Slice | Implementation | User review |
| --- | --- | --- |
| 1 | Complete | Approved 2026-11-15 ("Sure make slice two"), after three art revisions |
| 2 | Complete | Reviewed 2026-11-15: hood down and smaller head requested and done |
| 3 | Complete | Pending |
| 4 | Complete | Pending |
| 5 | Not started | Pending |
| 6 | Not started | Pending |
| 7 | Not started | Pending |
| 8 | Not started | Pending |
| 9 | Not started | Pending |

**Next action:** start Slice 5 (food content and the ramen scene cameo).

**Where the code is saved:** Kushal's new GitHub repository could not be reached from the build session
(not visible to it under the names tried). Until it is attached, every commit is also pushed as a backup to
branch `claude/intelligent-tesla-tb3db1` of `Kushal0217/pokedex-ops`.

## Slice 4 — Personal project collection

**Built:**
- One ordered data source, `src/features/projects/projects.ts`. Pokédex Ops Skill is the only entry, first in
  both views, with the approved draft blurb and status "In progress". It has no links because no URL has been
  supplied, so no link buttons are rendered.
- Badge case viewer (`ProjectViewer.tsx`) with two tabs over that list: **Badges** (grid of badge buttons plus
  a detail panel) and **All projects** (every name, blurb, status and link readable at once).
- Persistent **Badge case** (with icon) and **Projects** buttons in the sticky header, beside Just the facts.
  Projects opens the full list directly. `#projects` and `#badges` in the address open each tab.
- Original badge family in `Badge.tsx`: shared ink rim, facet highlight and shadow; shape, accent and pixel
  emblem vary. Pokédex Ops is a teal hexagon with a database stack and wrench. Projects without a design get
  a consistent default badge.
- Adding a project is one entry in `projects.ts` (plus an optional design in `Badge.tsx`).

**Checks run (cloud session, 2026-11-15):**

| Check | Result |
| --- | --- |
| `npm run build` | Passed. |
| `npm run check:build` | Passed, and now also fails the build if fixture text reaches `dist/`. |
| `DEV_URL=http://localhost:5173/ node scripts/check-site.mjs` | Passed: 511 checks. |

Added for this slice: both header buttons visible on the first screen; Projects opens on All projects with
the blurb, status and no link, without touching a badge; Pokédex Ops is first in both views; the badge detail
text equals the list text; tabs switch with arrow keys without closing the viewer; a badge is selectable by
keyboard; Escape and the close control return focus to whichever button opened the viewer; the avatar does
not move while the viewer is open; direct `#projects` / `#badges` links work. With the dev-only fixture
(`?fixture=projects` on `npm run dev`, 11 badges) at 1280px and 360px: no overflow, no clipped badge names,
the last badge is reachable and selectable, supplied links appear in both the detail panel and the list.

**Defect found and fixed:** W A S D moved the avatar underneath the facts view and the badge case. Movement
keys are now off while any dialog is open.

**Assumptions recorded:**
- The badge detail is an inline panel inside the Badges tab rather than a third stacked dialog.
- GSAP is still not installed. The spec names it for coordinated animation, but so far every transition is a
  short CSS one; adding the library for these would only add weight. Kushal can ask for it.
- Clicking the avatar does not open the case (the PRD marks that as optional).

**Limitations:**
- The many-badges layout is only exercised with placeholder fixture entries, which never ship.
- Only links starting with `https://` are rendered; anything else in the data is dropped.

## Slice 3 — Town and atmosphere

**Built:**
- Four places from one data list (`src/features/world/places.ts`): Profile, Ramen shop, Stadium, Airport.
  Home and gym are omitted until there is approved content.
- Two layouts generated from that list: a broad town with a crossroads on screens wider than 760px, and one
  winding vertical path on phones (normal page scrolling, no panning or snapping). Same building art, labels
  and interactions in both.
- New original building art: profile studio, stadium (blue-and-garnet seating, no crest), airport terminal
  with control tower. Each has its own night lighting through the shared `--glow` token.
- Profile opens a short introduction with the resume; Stadium and Airport open panels that say plainly what
  is not built yet. No flights, scores or other facts are implied.
- Production lighting: Auto / Day / Evening / Night. Auto uses the device clock only (Day 07:00-16:59,
  Evening 17:00-19:59, Night 20:00-06:59), re-checks when the page becomes visible or focused, and sets one
  timer for the next boundary. Manual choices are saved in `localStorage`; the mode is applied by an inline
  script before first paint. The temporary preview selector is gone.
- Walking now covers the whole town: obstacles per building and tree, a doorway into every place, and A*
  routing on a coarse grid for tap-to-walk.

**Checks run (cloud session, 2026-11-15):**

| Check | Result |
| --- | --- |
| `npm run build` | Passed. |
| `npm run check:build` | Passed. |
| `node scripts/check-site.mjs` against `vite preview` | Passed twice in a row: 408 checks. |

Added to the script for this slice: every place opens by keyboard (Enter or Space) and by tap/click, closes
by Escape and by its close control, and returns focus to its own label; both layouts list the same four
places in the same order; Stadium and Airport state they are unfinished; Profile links the resume; Auto
resolves correctly at 06:59, 07:00, 16:59, 17:00, 19:59, 20:00, 23:30 and 03:00, both before the app loads
and after; a page left open across 17:00 changes mode; a changed device clock is picked up when the page
becomes visible; a manual choice persists across reload and Auto returns to the clock; the selector works
with arrow keys and with `localStorage` blocked; the page never calls geolocation or the permissions API for
it; no request leaves the site's own origin.

**Defect found and fixed:** an Escape pressed within a frame or two of a dialog opening could close the
dialog underneath it (the dialog library registers its layers slightly late). Escape is now handled by an
explicit stack in `SceneDialog.tsx`, updated before paint.

**Assumptions recorded:**
- The Profile panel names Capital One and Dallas, TX. Both are on the public resume; edit
  `src/features/profile/profile.ts` to change or remove them.
- "Food stop" is served by the ramen shop's menu rather than a separate building (the slice lists a
  "ramen/food area"). Kasama stays labelled as a real restaurant, separate from the fictional shop.
- The stadium uses blue and garnet stripes as a nod to Barcelona; no crest or official mark is drawn.
- Badge case and Projects controls are not on the first screen yet; they are Slice 4.

**Limitations:**
- Headless Chromium only; no physical phone, Safari or Firefox.
- Lighting contrast was reviewed by eye in screenshots, not with an automated contrast audit.
- A real sunrise/sunset is deliberately not modelled.

## Slice 2 — One complete exploration loop

**Built:**
- Map to interior to menu loop: the "Ramen shop" label (or the building itself) opens an illustrated interior
  (`src/features/food/RamenInterior.tsx`); its wall menu board is a real button that opens the favorites menu.
- Shared scene/dialog behaviour in `src/shared/ui/SceneDialog.tsx` (Radix Dialog): focus trap, Escape, visible
  close control, inert and scroll-locked background, focus returned to the launching control.
- "Just the facts" (`src/features/facts/`): persistent button in the sticky header and inside every scene
  header; plain view with resume download/open and email, phone, LinkedIn and GitHub links. `#facts` in the
  URL opens it directly. `public/resume.pdf` is the selected resume, unchanged.
- Optional avatar movement (Kushal asked for it): W A S D anywhere, arrow keys while the map has focus, or
  tap/click the ground. Walk frames for front, back and side. Walking up into the doorway enters the shop.
  Position is written straight to the element; React re-renders only on pose changes.
- Reduced motion: no walk animation frames, tap-to-walk places the avatar instantly, dialogs open without
  transitions. All content stays reachable.

**Revision (2026-11-15):** at Kushal's request the hood is down: the head and hair are visible in all
walk directions and the hood rests against the upper back. Build and all checks re-run and passed.

**Checks run (cloud session, 2026-11-15):**

| Check | Result |
| --- | --- |
| `npm run build` | Passed. JS 90.9 kB gzip, CSS 4.3 kB gzip. |
| `npm run check:build` | Passed: no private files in `dist/`; `dist/resume.pdf` identical to `source-assets/resume.pdf`. |
| `node scripts/check-site.mjs` against `vite preview` | Passed: 224 checks over desktop 1280x800, phone 390x844 (touch), narrow phone 320x568 (touch), reduced motion, and a short 1024x520 window. |

What the script exercises: enter by click, tap and keyboard; menu shows Kasama / Chicago with no rating or
date; Escape closes only the top layer; focus returns to the menu board, then to the place label, then to
whichever control opened the facts view; Tab stays inside the open dialog; the map is hidden from assistive
tech and not clickable under a modal; map scroll position is unchanged after closing; every facts link has the
expected target and the served resume matches byte for byte; W A S D and arrow keys move the avatar, arrows do
not steer when focus is outside the map, a held key stops on window blur, the avatar cannot leave the scene;
tapping the ground walks there; selecting the building opens it at once; walking into the doorway enters; no
console errors; no horizontal overflow in any state.

**Defects found and fixed during checks:**
- Under reduced motion one Escape press could close two stacked dialogs; each press now closes one layer.
- Returning focus scrolled the map in a short window; focus is now restored without scrolling.
- The sticky header and map label drew above open dialogs; dialogs now sit on top.
- Tap-to-walk stopped at the menu stand; the avatar now detours around it.

**Assumptions recorded:**
- "Sure" was read as yes to keyboard walking as well as click-to-walk.
- GSAP is not installed yet: the walk needs per-frame collision, and dialog transitions are two CSS keyframes.
  It joins when a coordinated timeline is first needed (badge case, Slice 4).
- The interior uses a fixed warm palette in all lighting modes (PRD: indoor panels may share one readable surface).
- The Naruto cameo is not in the interior yet; it belongs to Slice 5.
- The lighting selector is still the temporary preview; production Auto/Day/Evening/Night is Slice 3.

**Limitations:**
- Not tested on a physical phone or in Safari/Firefox; checks ran in headless Chromium only.
- Screen-reader behaviour was checked through roles, names and `aria-hidden`, not with a screen reader.
- Tap-to-walk pathing is a simple detour that suits this one-obstacle yard; the full town (Slice 3) will need more.
- The email address and phone number are published in the facts view, as the PRD specifies.

## Slice 1 — Visual foundation

**Built:** React + TypeScript + Vite project. Kushal's pixel sprite (`src/features/world/kushalSprite.ts`),
the ramen-shop exterior as original SVG (`RamenShopExterior.tsx`), and the open food menu
(`src/features/food/`), composed for desktop (scene beside menu) and phone (stacked). Day, evening and night
share the same artwork: only the tokens in `src/theme/tokens.css` change, and lantern/window/doorway light
layers fade in through one `--glow` token. A temporary "Lighting preview" selector switches modes.

**Preview:** `npm install`, then `npm run dev` (or `npm run build && npm run preview`).
Same-Wi-Fi phone preview: `npm run dev:lan` and open the "Network" URL Vite prints on the phone. The computer
must stay on and reachable; `localhost` on the phone means the phone itself.

**Checks run (cloud session, 2026-11-15):**

| Check | Result |
| --- | --- |
| `npm run build` (`tsc --noEmit` + `vite build`) | Passed. JS 72.6 kB gzip, CSS 3.4 kB gzip. |
| `npm run check:build` | Passed: 11 files in `dist/`, none matching `private/` by hash, no raster images, no CSV. |
| `node scripts/review-shots.mjs` against `vite preview` | Passed at 1280x800, 390x844 and 320x640 in all three modes: no horizontal overflow; name, menu, Kasama, Chicago and the shop label visible; menu closes with its close button and reopens from the shop label by keyboard. |
| Screenshots viewed | Desktop and phone, day/evening/night. Fixed during review: selector marker wrapping, menu rule lines crossing text, phone label covering the avatar. |

**Revision after first review (2026-11-15):** Kushal asked for more sprite detail and a lighter avatar.
The sprite was redrawn at 24 x 42 pixels (was 16 x 28) at the same on-map size: hood highlight and
drawstrings, quilted jacket seams and zipper, brows, eyes and short facial hair, jeans highlights, sneaker
laces and soles. Skin, hoodie and jacket tones were lightened in all three modes. The building gained wood
grain, plaster flecks and stone joints, and the grass gained flowers. Build, `check:build` and
`review-shots` were re-run and passed. "Lighter" was read as lighter colours; confirm with Kushal.

**Second revision (2026-11-15):** beard removed from the avatar; trees and bushes redrawn with lobed
canopies, lit and shaded clumps, pixel leaf sprigs, fruit, bark and root flare. Bush blossoms (red with a white outline) were removed at Kushal's request. Build,
`check:build` and `review-shots` re-run and passed.

**Assumptions recorded:**
- Role line "Software Engineer" is taken from the resume.
- The menu lists only Kasama (Chicago). No rating, note, dish or link is shown because none was supplied; the Beli link is omitted until its URL exists.
- The face shows only what the reference shows clearly: dark hair, brows and eyes. The beard was removed at Kushal's request.
- Fonts (Pixelify Sans, Nunito; both SIL OFL) are bundled locally, so there are no runtime calls to a font service.
- GSAP, Radix and Phaser are not installed yet; they join in the slices that first need them (2 and 7).
- `private/` (avatar reference photo) is git-ignored and never built. `source-assets/` holds the resume and the flight CSV template until the slices that use them.

**Limitations:**
- The sprite has one front-facing idle frame; walking frames come with avatar movement in Slice 2.
- The menu is an inline panel, not yet a modal dialog with focus management (Slice 2).
- Contrast was checked by eye, not with an automated contrast audit.
- No LAN URL could be produced from the cloud session; the command above prints it on a local machine.

**Files:** `src/**`, `scripts/check-build.mjs`, `scripts/review-shots.mjs`, `index.html`, `vite.config.ts`,
`tsconfig.json`, `package.json`, `package-lock.json`, `.gitignore`.
