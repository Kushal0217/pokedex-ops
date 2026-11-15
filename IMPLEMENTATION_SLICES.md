# Implementation slices

Use PRD.md as the product specification and this file as the implementation order. Implement slices in order with checks between each. Begin with Slice 1 only and pause for the initial visual review. After approval, continue remaining slices autonomously.

## Working agreement

- Read the PRD, source assets, and current code before starting. Respect all confirmed decisions.
- Keep each slice runnable and reviewable. Implement only the current slice and the minimal foundation it needs; defer future features.
- Within the current slice, independently fix discovered defects and finish the completion checks before reporting.
- At each slice boundary, record preview details, desktop and phone screenshots when browser capture is available, checks performed and results, remaining limitations, and files changed. Report meaningful progress without waiting for routine approval after Slice 1. If screenshots cannot be captured, say so and give exact manual review steps.
- Update BUILD_PROGRESS.md with the slice status, evidence, unresolved issues, and next slice. Mark implementation complete and review pending separately from user accepted.
- Stop for Kushal’s visual review after Slice 1 only. Time passing or silence is not that approval. Once the visual direction is explicitly approved, advance through remaining slices automatically after completing checks. Incorporate user feedback when received and keep progressing on independent work.
- Do not describe a slice as done when a required check failed or its key interaction is a placeholder. Missing user data may use the explicitly allowed empty state.
- Use meaningful checks for real behavior and edge cases; avoid tests that merely repeat implementation details.
- Keep approved art direction and interactions consistent across later slices. Refactor shared pieces when needed rather than duplicating them.
- Do not deploy or publish during these slices without a separate request.

## Slice 1 — Visual foundation

**Build:** A polished, runnable sample of Kushal’s avatar, ramen-shop exterior, and an open food-menu panel, composed for desktop and phone. Show day, evening, and night using shared art and a temporary preview selector. Establish palette, typography, illustration perspective, sprite scale, panel borders, lighting, and spacing. Use Kasama as the only confirmed restaurant; no invented review or rating.

**Done when:** The avatar follows the supplied reference; the original photo is not exposed in public output; the exterior, sprite, and menu feel coherent; text and controls remain readable in all three modes; the phone scene fits without horizontal overflow; screenshots or clear preview instructions are supplied for all treatments. Keep the menu panel visible for art review—full navigation behavior belongs to Slice 2.

**Review focus:** Approve the art direction before producing the complete town, interiors, or footballer sprites.

## Slice 2 — One complete exploration loop

**Build:** Connect the initial map location to a working ramen interior and readable favorites menu. Establish reusable scene/dialog behavior, close/back controls, click/tap/keyboard activation, optional avatar movement, and reduced-motion handling. Add the labeled Just the facts view and the supplied resume/contact links so essential content is already accessible.

**Done when:** A visitor can enter, open the menu, close it, and return without losing map scroll position; focus returns to the correct launching control; Escape works; touch controls fit; reduced motion preserves access; resume and contact actions work; no input gets trapped or background content remains incorrectly interactive under a modal.

**Review focus:** Navigation clarity and the complete experience on a phone.

## Slice 3 — Town and atmosphere

**Build:** Expand to the approved map locations: profile, stadium, ramen/food area, and airport. Use shared location data for the broad desktop town and continuous vertical phone path. Include simple useful previews or explicit coming-in-later-slice states for unfinished stadium/airport content during development; do not represent those features as complete. Add production Auto/Day/Evening/Night behavior, saved preference, local-time ranges, and a persistent facts action. Home and gym stay omitted until approved content exists.

**Done when:** Every location can be reached by keyboard and touch; desktop and phone contain the same locations; the phone uses normal vertical scrolling; theme resolution follows PRD ranges and storage fallback; visibility/time changes refresh Auto; no geolocation request occurs; readable controls persist in every lighting mode.

**Review focus:** Town composition, mobile path, and lighting consistency.

## Slice 4 — Personal project collection

**Build:** The original badge case and directly accessible All projects tab, backed by one ordered data source. Pokédex Ops is first, using the approved draft blurb. Include valid project links only when supplied. Make the case scalable beyond eight projects with a default badge option.

**Done when:** Visitors can read all blurbs and use available links without opening a badge; badge details and list data agree; tabs and dialogs support keyboard use; a temporary development fixture with more than eight items demonstrates layout scalability without publishing invented projects; missing URLs do not become fake buttons.

**Review focus:** Badge design, scannability, and ease of adding projects.

## Slice 5 — Food content and ramen scene

**Build:** Finalize the editable local food snapshot and restaurant-list presentation; import only user-supplied entries. Include Kasama in Chicago, the optional Beli link when supplied, and the original small Naruto/Iruka/Kakashi/ramen-owner vignette. Keep the fictional setting distinct from real restaurant names.

**Done when:** All food entries are readable together, updating the data changes the menu without map edits, missing ratings/links are omitted, there is no last-updated timestamp, and cameo art fits the approved style without blocking controls. If no further recommendations are supplied, Kasama alone is a legitimate initial list.

**Review focus:** Menu readability and the cameo’s visual fit.

## Slice 6 — Airport and CSV pipeline

**Build:** Airport interior with Route map and All flights tabs, search/year filters, approved totals, local airport lookup, and a robust CSV-to-site-data import. Follow the PRD CSV schema and flown-only publication rules. Keep the source CSV outside the public build.

**Done when:** A supplied approved dataset populates list, routes, filters, and totals consistently; quoted CSV fields, invalid records, missing metadata, and likely duplicates are handled as specified; canceled/booked/uncertain rows are excluded; malformed replacement input preserves valid prior data. With no user data, a deliberate empty state is complete UI behavior. Use clearly isolated synthetic development fixtures to check imports, not invented public history. Explain how to replace the CSV and rebuild.

**Review focus:** Accurate data and a readable map/list on phones.

## Slice 7 — Penalty mechanics

**Build:** A playable stadium with Kushal and an NPC goalkeeper first. Implement free goal aiming, keyboard arrow aiming, centered default target, hold-to-charge/release, broad sweet spot, low/overcharge effects, goal/save/miss outcomes, and optional five-shot rounds. Lazy-load the game and stop its loop when closed. Use simple temporary art only where needed for mechanical review.

**Done when:** Mouse, touch, and keyboard each aim and shoot; a release resolves exactly one shot; key repeat cannot create duplicate actions; pointer cancellation, focus loss, tab switching, and closing reset safely; keeper behavior does not always counter the target; fifth-shot state and replay work; resizing preserves target position; reduced-motion results are readable. The game never blocks access to portfolio content.

**Review focus:** Charge timing, aiming feel, fairness, and responsiveness before multiplying character art.

## Slice 8 — Stadium art and character roster

**Build:** Finish the stadium presentation and all seven player choices: Kushal, Messi, Ronaldo, Neymar, Haaland, Mbappé, and Lamine Yamal. Add restrained original celebrations and result feedback. Preserve identical gameplay ability across the roster.

**Done when:** All players are selectable with readable names and clear selection, all share the same mechanics, art follows the approved sprite scale, animations respect reduced motion, and mobile controls remain unobstructed. Recheck Slice 7’s gameplay behavior after replacing art.

**Review focus:** Character treatment, shot animation, and overall stadium polish.

## Slice 9 — Cameos, release quality, and maintenance

**Build:** Finish Herobrine’s corner-peeking hover/tap/keyboard vanish behavior, settle cross-scene visual details, and write maintenance/local-run/static-build instructions. Remove temporary development placeholders and fixtures from the public experience. Preserve the selected resume unchanged.

**Done when:** Walk through the complete site on desktop and a narrow phone viewport, using keyboard-only and reduced-motion modes as well. Check all real links, dialog focus, browser back behavior where navigation uses URL state, readable day/evening/night contrast, and no horizontal overflow. Confirm stadium assets load only when needed and its loop stops on exit. Measure a production build with a documented mobile/network profile, report transfer size and loading results, and address blockers to the PRD’s couple-of-seconds usability target. Confirm no avatar reference photo, raw CSV, credentials, private emails, or unused sample data enters the public build.

**Review focus:** A coherent, usable whole and clear instructions for updating projects, food, flights, resume, and artwork. Deployment remains a separate user decision.

