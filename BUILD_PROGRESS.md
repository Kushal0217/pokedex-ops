# Build progress

| Slice | Implementation | User review |
| --- | --- | --- |
| 1 | Complete, awaiting visual review | Pending |
| 2 | Not started | Pending |
| 3 | Not started | Pending |
| 4 | Not started | Pending |
| 5 | Not started | Pending |
| 6 | Not started | Pending |
| 7 | Not started | Pending |
| 8 | Not started | Pending |
| 9 | Not started | Pending |

**Next action:** wait for Kushal's explicit approval of the visual direction (or requested changes). Then start Slice 2.

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
