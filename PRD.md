# Playable Portfolio — PRD

**Date:** November 14, 2026  
**Status:** Working draft for implementation  
**Purpose:** A personal website that feels like exploring a small indie game world while making it easy to understand who Kushal is and find his resume.

## Product summary

Build a responsive, explorable world that introduces Kushal through a small stylized avatar, favorite places, and personal-interest cameos. The site should feel playful and personal, but it is not a game visitors have to complete. Work achievements belong in the resume; the site gives a brief professional introduction and a direct path to that resume.

## Goals

- Make the first screen feel like a welcoming, original indie game world.
- Make Kushal’s identity and the resume link easy to find immediately.
- Let curious visitors explore a few personal details through small interactions and easter eggs.
- Keep the site easy to extend with new places and personal interests.
- Make the experience work on phones, keyboards, and reduced-motion settings.

## Non-goals

- Portfolio navigation never requires skill, quests, scores, or unlocks. The optional stadium penalty game may have goals, saves, misses, and a local round score. No battle system is required.
- Keep workplace achievements in the resume. Personal projects may appear as named, linked badges in the character’s badge case.
- Do not simulate a production AI agent or imply that a demo performs real company work.
- Do not require a backend, account, database, analytics, or external API at runtime.
- Do not use a franchise as the site-wide art direction or copy official artwork, logos, maps, fonts, or interface assets. Requested franchise cameos are small, contained fan-art easter eggs.

## Audience and entry points

1. **Recruiter or hiring manager:** should immediately see who Kushal is and be able to open or download the resume.
2. **Curious visitor:** can explore the map and find a few personal-interest details.

The page opens directly on the world map. No splash screen, “press start,” or intro sequence. The first screen includes:

- Kushal’s name and a short professional identity line
- A clear **Explore** cue
- Clearly labeled **Badge case** and **Projects** controls; Projects opens the full readable list directly
- A persistent **Just the facts** button linking to a plain, readable resume/contact view

The facts view remains available from every screen and never depends on map progress.

## Core experience

1. Visitors land directly on the map and can identify the site owner and resume action.
2. Visitors select a labeled place by mouse, touch, or keyboard.
3. The character may walk briefly toward that place, but the content opens promptly and cannot be delayed by animation.
4. A place opens a concise panel or small scene about a personal interest.
5. Visitors can close the scene and return to the map, or open the facts view at any point.

No place is locked. There is no required order, map-wide failure state, or information hidden behind game completion. The stadium alone includes optional scoring and unsuccessful shots; visitors can exit at any time.

## Information architecture

### World map

The map is the main navigation. Initial place ideas:

- **Work / profile:** a short professional introduction and resume link. Do not show achievement metrics or project case studies here.
- **Stadium:** an optional hold-to-charge penalty game with selectable players and an NPC goalkeeper; Barcelona remains Kushal’s club.
- **Ramen shop:** an optional Naruto fan-art scene with Naruto, Iruka, Kakashi, and the ramen-shop owner from the series.
- **Food stop:** a separate note for Kasama in Chicago. Keep this real restaurant distinct from the fictional Naruto ramen shop.
- **Airport:** a flight-history terminal with Route map and All flights views, populated from a user-provided CSV.
- **Home or gym:** optional personal-interest panels if they add details Kushal wants to share.

Places are modular. New personal interests can become new map locations without changing the overall navigation.

### Desktop and phone layouts

- On desktop, show a broad top-down town map.
- On phones, arrange the same locations along an illustrated vertical village path that visitors scroll naturally.
- Keep the mobile scene visually continuous, with buildings, paths, and scenery rather than a generic stack of cards.
- Reuse the same location data, labels, artwork style, and interactions across both layouts.
- Keep the “Just the facts” action visible while scrolling. No horizontal panning, pinch zoom, or forced scroll snapping is required.
- Open location content in a readable mobile panel with a clear close button, preserve the map scroll position, and restore focus to the launching location on close.
- Do not attach avatar motion to every scroll event. Move the avatar only after a location is selected, with reduced-motion support.
- Position the optional cameos so they remain discoverable and tappable on phones.

### Professional content

The site should keep work content brief:

- Show a short role or professional identity line.
- Provide a prominent link to the selected resume.
- Workplace achievements and metrics belong in the resume. The separate badge case and All projects tab may show approved personal-project blurbs and links.

### Just the facts

A simple, readable view that contains:

- Name and a short role line
- Downloadable resume using the attached site asset, **[resume.pdf](resume.pdf)** (a byte-for-byte copy of the selected file, CV-kushal-gaddam-resume (1).pdf)
- Email: **Kushalgaddam171@gmail.com**
- Phone: **(850) 518-5547**
- LinkedIn: **https://www.linkedin.com/in/kg15**
- GitHub: **https://github.com/Kushal0217**

Attach **resume.pdf** as a site asset when handing this PRD to the implementation assistant. Keep the facts view readable without map art or animation.

## Personal details and easter eggs

### Avatar

The map character should be a small, stylized likeness of Kushal based on the attached reference photo, **[avatar_reference.png](avatar_reference.png)**. The photo is an art reference; do not publish the original photo on the site unless separately requested.

![Avatar reference photo for stylized likeness only; do not use as website content](avatar_reference.png)

Reference cues: dark hoodie under a black jacket, light blue jeans, and white sneakers. Keep the character simple and recognizable at small map scale. Do not invent detailed facial features that are not clear in the reference.

### Naruto ramen-shop cameo

Include a small, optional fan-art vignette at the ramen shop with Naruto, Iruka, Kakashi, and the ramen-shop owner from Naruto. Keep the cameo local to the ramen scene; it should not define the site-wide visual style or be necessary for navigation. Use original fan-art rather than official screenshots or extracted production art.

### Herobrine easter egg

Hide a small Herobrine cameo peeking from behind a building corner or other map edge. When the pointer hovers over him, he vanishes with a quick, subtle effect. On touch screens, tapping him triggers the same effect; keyboard focus and activation should also work. The easter egg is optional, never blocks a control, and contains no essential information. It may reappear after a page reload.

### Soccer and food

- The stadium panel can mention Barcelona as Kushal’s soccer club. Do not use an official crest unless Kushal supplies an approved asset.
- Include Kasama in Chicago as a real restaurant note, separate from the fictional ramen-shop scene. Do not call Kasama a ramen shop.

### Ramen-shop food favorites and Beli

Entering the ramen shop opens a small illustrated interior. Selecting the menu reveals Kushal’s food favorites, including Kasama in Chicago, and a “Find me on Beli” link once Kushal supplies the actual profile share URL. All favorites must be reachable in one clear interaction; no hidden-object search is required. Label the real restaurant list separately from the fictional ramen setting.

Food recommendations are a manually refreshed snapshot supplied by Kushal from Beli, not an automatic integration. Accept a user-provided export, screenshots, or a written list and transcribe only the selected approved entries. Store the resulting data in a small editable local file, separate from the artwork.

Each entry can include restaurant name, city, optional rating, short note or favorite dish, and optional restaurant link. Do not display a “Last updated” date or other freshness timestamp in the restaurant interface. Do not invent ratings, ranking positions, restaurant details, or links. The profile share URL is pending; omit the external Beli action until it is supplied.

Kushal will update the snapshot occasionally. Replacing the food data should not require changing the map, illustrations, or components. No live Beli API, credentials, scraping, automated sync, or runtime account connection is required.

### Stadium penalty game

Entering the stadium opens an optional compact penalty-shootout scene. Visitors can leave immediately without completing a shot or round. This game does not unlock projects, resume access, personal details, or any other portfolio content.

**Player selection:** Kushal, Lionel Messi, Cristiano Ronaldo, Neymar, Erling Haaland, Kylian Mbappé, and Lamine Yamal. Use small stylized original character illustrations, with visible names and selected states. Kushal’s character follows the supplied appearance reference. All players have identical shot mechanics and ability in version 1; appearance and brief celebrations can distinguish them. Do not imply endorsement.

**Shot sequence:**

1. Choose a player, then tap or click anywhere inside the goal to place a visible aiming marker. Default to the center so shooting works immediately; allow repositioning before each shot.
2. Hold the Shoot button to charge a visible power meter. Release to kick.
3. Low power produces an easier-to-save shot. A generous, visibly marked sweet spot produces a strong, accurate shot toward the selected point. Overcharging reduces accuracy and can produce a miss.
4. The NPC goalkeeper commits to a direction when the shot is released. The keeper must not read and always counter the selected aim. Outcomes use the selected aim, charge quality, and a modest amount of variation; a sweet-spot shot is an advantage, not a guaranteed goal.
5. Show a brief goal, save, or miss result and a clear next-shot control. Visitors may replay indefinitely or play an optional five-shot round.
6. In a five-shot round, show shot number and goals scored; after shot five, offer Play again and Back to town. Scores are session-only, with no leaderboard or account.

**Controls and feedback:** Mouse or touch press-and-hold starts charging, release kicks. Provide Space or Enter hold/release behavior while the Shoot control is focused; ignore repeated keydown events so they cannot restart charging or fire duplicate shots. Aiming and player selection are keyboard accessible. With the goal aiming control focused, arrow keys move the marker within the goal bounds; expose concise instructions and the marker position in accessible text. Use normalized coordinates so aiming stays aligned when the scene resizes. Give phone users generous touch tolerance; charge quality may introduce dispersion around the chosen point. Include concise on-screen instructions and a text result for every shot.

Use a capped, single-fill meter rather than a rapidly looping meter. Keep the sweet spot broad enough for casual visitors. Distinguish sweet spot and overcharge through labels or shapes as well as color. Charge feedback must remain readable with reduced motion. Avoid screen shake or rapid flashes.

Handle pointer cancellation, lost focus, and tab switching by safely canceling charge and returning to a ready state. The Shoot control must not remain stuck charging, trigger a second shot, or scroll the page when Space is used. Disable duplicate submissions during the short shot-resolution animation. On touch screens ensure aiming and shooting controls fit comfortably without covering the goal.

With reduced motion, preserve the same aiming and charge mechanics while replacing ball travel and celebrations with brief or immediate state changes and readable results. Load game artwork and logic when the stadium is opened, not before the main map becomes usable.

### Airport and flight log

Selecting the airport opens a small illustrated terminal containing a readable flight log. Its two tabs are **Route map** and **All flights**.

- **Route map:** a flat world map with airport markers and curved connections. Selecting a route reveals the flights along it and the count flown. Treat outbound and return directions explicitly in details. Use a lightweight local map asset and airport-coordinate lookup; no spinning 3D globe or paid map API is needed.
- **All flights:** a compact airport-style board listing date, airline, flight number, origin, and destination. Support year filtering and search by city or airport code. All records must be accessible without selecting map lines. On phones use compact stacked rows with readable routes, dates, and airline labels.
- Display totals for flights taken, airports visited, and countries visited. Count flight legs rather than bookings; count distinct airports and countries from the departure/arrival airports of flown legs. Do not treat connections as evidence that Kushal visited a city or country outside its airport. Label the country statistic “Countries flown to/from.”
- Use only a brief optional board transition when filters change, with immediate updates under reduced motion. Load route-map art and data when the airport is opened.

### Flight data handoff and maintenance

Muse will produce a CSV from Kushal’s flight emails outside this website build. Claude reads that supplied CSV and imports approved flight records into a local structured data file used by both airport tabs and totals. The website requires no email access, Flighty connection, calendar sync, backend, or scheduled importer. Keep this as an occasional file import workflow, consistent with the latest decision.

Expected CSV columns:

`date,airline,flight_number,origin_airport,destination_airport,status`

Use ISO dates (YYYY-MM-DD) and three-letter IATA airport codes. Each row represents one flight leg. Flight number and airline may be blank when unknown. Supported status values are `flown`, `booked`, `canceled`, and `uncertain`. Only `flown` records appear in the public history or totals. Booking emails alone do not prove a flight was taken; Muse should preserve uncertainty for review instead of guessing.

Import robustly with a CSV parser that supports quoted fields and UTF-8. Normalize codes and statuses, flag invalid dates or airports, and detect likely duplicates using date, origin, destination, and available flight number. Do not merge distinct same-route flights automatically when uncertain. Preserve the selected source CSV for future reimports outside the public deployment; publish only the approved derived data.

Resolve airport names, coordinates, and country codes from a local lookup with a recorded source/license. Never guess unknown coordinates; retain valid flight rows in the list while flagging missing map metadata for repair. Compute totals consistently from valid approved data.

The CSV must exclude booking references, ticket numbers, seat numbers, passenger details, and email bodies. Do not publish raw email material. Retain the last valid imported data if a replacement file is malformed. Include brief maintenance instructions explaining how to replace the CSV and rebuild.

The flight history file is not supplied yet. Show a deliberate, concise empty state until approved data is available; do not invent flights, routes, or travel totals. The bundle includes a header-only `flights_template.csv` for Muse’s output format. The CSV is not a live account connection, and the site should not claim automatic synchronization or complete lifetime coverage beyond the supplied records.

### Personal project badge case

The character carries a “Badge case” that serves as the expandable home for personal projects. Provide a clearly labeled persistent button with a small badge-case icon; it must be discoverable without clicking the avatar or visiting a specific building. An optional click on the avatar may also open it.

Opening the case reveals original collectible-style badges, one per approved project. Use a shared badge shape family, illustration style, palette, and interaction system; do not copy Pokémon gym badges. Every badge has a readable project name. No badges are locked, and viewing them requires no gameplay.

Selecting a badge opens a concise project detail panel containing a short approved description and clearly labeled links such as “Live demo,” “Source code,” or “Read more,” where valid links exist. A project may have several links. Project text and links are real HTML. Do not invent projects, URLs, metrics, or completion status. Omit unavailable link actions. Unpublished projects may be marked “In progress” only when approved.

The case is distinct from work achievements: workplace accomplishment stories and metrics remain in the resume. Personal projects may be described and linked here. Pokédex Ops Skill is confirmed as the first badge and the first entry in the project list. Other projects require selection by Kushal.

Use a responsive grid inside the case: it can grow beyond eight badges, scroll vertically on phones, and preserve readable labels. Adding a project should require one structured content entry and an optional badge illustration, without changing the town layout. A consistent default badge may be used before custom art exists. Do not display a fixed row of empty slots suggesting that only eight projects can exist.

Escape or a visible close control returns to the map and restores focus to the case button. Project selection and links are accessible by keyboard and touch. Badge hover/focus effects are subtle and respect reduced motion. No progress score or completion gate is attached to the case.

Initial project:

- **Name:** Pokédex Ops Skill (short display name: Pokédex Ops).
- **Order:** first badge and first entry in All projects.
- **Draft blurb, grounded in the selected resume:** “An eval-driven MCP server and Agent Skill for PostgreSQL/Aurora operations, using Pokémon data to explore query analysis, index proposals, health checks, and guarded index changes.”
- **Status:** in progress, as described in the selected resume; keep this editable.
- **Links:** repository, demo, and write-up URLs are pending. Omit unavailable link buttons and never substitute a fabricated URL.
- **Presentation:** an original database/tool-themed badge with a distinct accent; this is a project entry, not a battle scene.

### All projects tab

The project viewer has two clearly labeled tabs: **Badges** and **All projects**. Provide a visible Projects navigation control that opens All projects directly, alongside the Badge case entry point. Visitors can reach the complete readable project list without opening any badge.

All projects shows every approved project in one scrollable list. Each entry includes its name, a short blurb, optional approved status, and available links to its demo, source, or write-up directly in the list. Reading every blurb or opening a project link requires no individual detail-panel interaction. Use a compact, readable layout rather than oversized cards with excessive whitespace.

Both tabs use the same ordered project data. Pokédex Ops is first in both. Adding or editing a project must update both views automatically; do not maintain duplicate descriptions or link collections. Each project entry can store a stable ID, name, blurb, approved status, badge art, optional longer description, link array, and display order.

Tabs support keyboard navigation and expose their active state accessibly. All projects is easy to read on phones. Switching tabs must not lose project content, close the viewer unexpectedly, or require animation. A direct URL fragment may open the project list if straightforward for the chosen static-site structure.

## Visual direction

Use an **original hybrid indie-adventure style**: illustrated map scenery with small pixel-art details or character treatment. The mood should be warm, curious, and handcrafted, with enough restraint to feel like a personal portfolio rather than a full game.

The overall world and its buildings should use an original visual system. Franchise references belong only in the two small, requested easter eggs. Do not copy official assets, logos, maps, or interface designs.

Keep readable text and controls as real page content, not text baked into images. The prior generated images are mood references only and include incorrect placeholder text.

## Build sequence and visual consistency

Follow **IMPLEMENTATION_SLICES.md** in order. Begin with Slice 1 only. Each slice must meet its completion checklist and update BUILD_PROGRESS.md. Pause for Kushal’s visual review after Slice 1 only. After that approval, continue through remaining slices automatically, preserving their order and quality checks. User acceptance is distinct from implementation completion. Implement incrementally rather than generating the entire site in one pass.

Build in reviewable stages. Start with one polished visual sample: Kushal’s stylized avatar, the ramen-shop exterior, and an open menu panel shown together, including a phone layout. Establish their shared palette, perspective, sprite scale, typography, borders, and shadows before producing every building or interior. Then build the desktop and phone map composition, shared panel/navigation behavior, projects/food/flight-log views, the optional stadium game, and final cameo polish. Present the initial sample as a review checkpoint so style corrections can happen before the full asset set is produced.

Define shared color, typography, spacing, panel, and motion tokens. Use a consistent scenery perspective, lighting direction, and pixel scale for sprite details. The supplied avatar photo is an appearance reference, not a style reference. Avoid generic dashboard cards, glass effects, gradients, and icon collections that conflict with the game world.

### Local-time atmosphere

Default the world lighting to **Auto**, based solely on the visitor’s device-local clock. Do not request geolocation permission, infer location from IP, call a timezone/weather service, or send the detected time/timezone to a server. This is a stylized time-of-day effect, not an astronomical sunrise/sunset simulation.

Auto mode uses these local-hour ranges:

- **Day:** 07:00–16:59 — brighter scenery and clear colors.
- **Evening:** 17:00–19:59 — warm lighting and sunset accents.
- **Night:** 20:00–06:59 — darker scenery with lit windows and signs.

Provide a small labeled **Auto / Day / Evening / Night** selector, accessible by keyboard and touch. Store a manual preference locally so it persists across visits. Returning to Auto uses the current device time. If browser storage is unavailable, the selector still works for the session. Apply the resolved mode before the world paints where practical to avoid a bright flash on nighttime visits.

Re-evaluate Auto when the page regains visibility and at an appropriate time boundary using a lightweight timer. No continuous animation loop is needed to determine time of day. A device clock or timezone change should be picked up when the page becomes active again.

Reuse the same scenery, sprites, and layout across modes. Use palette tokens, selected shading layers, and window/sign lighting rather than downloading three full map images or applying one dark filter to every element. Keep readable text, controls, player identities, and the stadium’s aiming/charge feedback clear in all modes. Indoor panels may share a consistent readable surface. Respect reduced motion when switching modes and avoid forced animated transitions during initial load.

The first visual sample should demonstrate the shared avatar, ramen-shop exterior, and menu panel in day, evening, and night treatments without creating three separate asset sets.

## Interaction rules

- Every location has a visible label and clear focus/selected state.
- One click or tap opens a location; no precise movement or skill is required.
- Keyboard users can Tab through locations and press Enter or Space to open one. Escape closes a scene and returns focus to its launching control.
- Touch targets are comfortable on mobile and do not depend on hover.
- The avatar may automatically walk to a selected place, but movement is decorative and never required.
- Herobrine’s hover-to-vanish effect also works through touch and keyboard activation.
- Reduced-motion settings skip or simplify movement and transitions.
- No sound in version 1. If sound is added later, it starts muted with a persistent mute control.
- Important information is never conveyed only by animation, color, hover, or an easter egg.

## Content and extensibility

Keep map places and their text separate from map presentation. A new location should be addable as a content entry. Custom artwork or interaction code should be optional.

Suggested place fields:

- Title and short label
- Interest/category
- Short approved description
- Optional link or image
- Optional interaction type

Use only facts supplied or explicitly approved by Kushal. Do not invent personal history, favorite places, work claims, metrics, links, or affiliations. Keep private or confidential company details off the site.

## Platform and implementation constraints

- Static site with no backend; suitable for GitHub Pages.
- Multiple source files and optimized assets are allowed. Prefer maintainable source over one hand-edited HTML file.
- Use semantic HTML for controls, panels, and text. Use responsive SVG or layered art for the map; do not make the whole site one screenshot with fragile click coordinates.
- Keep dependencies small and use the recommended library approach below: GSAP for coordinated site animation, lazy-loaded Phaser for stadium gameplay, and optionally Radix for React dialogs and tabs.
- Keep the resume PDF and other scene art as separate assets.
- No external API calls are needed at runtime.

### Recommended library and asset approach

- **Main site:** use React + TypeScript with Vite, semantic HTML, responsive CSS, and custom SVG or optimized layered illustrations. Organize reusable components and typed content rather than one large HTML file. The site shell remains usable independently of the stadium engine.
- **GSAP:** use for coordinated avatar walks, badge-case opening, scene transitions, and cameo effects when a timeline improves clarity. Simple button states can use CSS. Respect reduced motion and cancel animations when their scene closes.
- **Phaser:** use for the stadium’s 2D gameplay, sprite animation, ball movement, goalkeeper, and shot state. Load it and stadium assets only when the stadium opens; stop its update loop and release resources when closed. Keep accessible player, aim, Shoot, and exit controls in HTML with clear coordination to the game.
- **Radix Primitives:** use custom-styled accessible dialogs and tabs within the React site; maintain the project’s illustrated visual system.
- **Aseprite:** an optional authoring tool for preparing pixel characters and animation sprite sheets. It is not a website dependency and must not be required to run the source.
- **Kenney Tiny Town:** not part of the recommended visual foundation or a required download. Generic tile assets may be used only as clearly temporary developer placeholders if useful; final scenery should follow the approved custom illustrated style. Do not let a tile pack dictate the finished art direction.
- Pin chosen dependency versions and include the lockfile. Avoid adding a second game renderer or animation library without a concrete need.

### Architecture and phone preview

Use feature folders for world/navigation, projects, food, flights, stadium, and shared UI/theme. React owns application navigation, accessible controls, and content views. Phaser owns the stadium simulation and rendering only. Define a small typed interface for selected player, aim, charge input, game events, and result state; avoid updating React on every animation frame. Create and destroy the game instance with its scene lifecycle.

Keep projects, restaurants, and approved imported flight data in separate typed content files. Put private source inputs and the avatar reference outside public assets; only the final character sprites, approved flight data, art, and resume should enter the production build. Add data-import scripts and update instructions. Use a lockfile, TypeScript checks, and production build commands.

For phone review on the same Wi-Fi, provide a Vite LAN preview command and the computer’s actual network URL where discoverable. Explain that the computer must remain running and reachable; localhost on the phone points to the phone itself. Do not bypass host validation or expose the server publicly by default. Hosted remote preview, account connections, deployment, and publishing remain separate actions requiring Kushal’s request.

## Performance, accessibility, and responsive behavior

- The initial map and primary controls should become usable within a couple of seconds on a typical phone connection.
- Load only the assets needed for the initial map. Defer any larger scene art until opened.
- Optimize image assets and use appropriately sized variants where useful.
- Support narrow mobile screens, touch input, and desktop layouts without hiding the map controls or facts action.
- Honor the operating system’s reduced-motion preference.
- Provide visible keyboard focus, meaningful labels, sensible focus order, and text alternatives for informative images.
- Maintain readable contrast; do not rely on color alone to communicate state.
- The map remains usable if animation is disabled.

## Version 1 scope

- A scalable personal-project badge case plus an All projects tab with every short blurb and available project links.
- Pokédex Ops Skill as the first project in both views; its external URLs are pending.
- A manually updated food-recommendation snapshot without a displayed update date.
- An airport terminal with Route map and All flights views, flight totals, and import support for a user-supplied CSV.

- Responsive explorable map with labeled, accessible places.
- A stylized avatar based on the supplied photo reference.
- Device-local Auto lighting with a persistent Auto / Day / Evening / Night override and shared artwork.
- Persistent **Just the facts** view with the attached resume and confirmed contact links.
- A concise work/profile panel with no achievement details.
- A Barcelona soccer detail and an optional penalty game with selectable characters, tap/click aiming anywhere within the goal, hold/release charging, an NPC keeper, and optional five-shot rounds.
- A small Naruto ramen-shop cameo.
- A separate Kasama-in-Chicago food note.
- A hidden Herobrine easter egg with hover, touch, and keyboard behavior.
- Other personal-interest panels only where approved.
- No work achievement scenes, Pokédex battle, quest gate, audio, analytics, or backend.

## Acceptance criteria

The first version is ready for review when:

- A first-time visitor can identify Kushal and open the resume without exploring.
- A visitor can open and close each map location by touch, mouse, and keyboard.
- Reduced-motion users can access the same content without movement-dependent steps.
- The avatar is guided by the supplied photo reference, while the original photo is not displayed.
- The Naruto and Herobrine cameos remain small optional details and do not block navigation.
- Work achievements are kept in the resume rather than repeated as interactive site content.
- Adding a personal-interest location does not require rebuilding the overall navigation.
- Adding a personal project does not require a new building or navigation changes; its badge and links appear through a content entry.
- The badge case supports more than eight projects without locked slots or unreadable labels.
- Visitors can read all project blurbs and use available project links in All projects without opening badges.
- Pokédex Ops Skill is first in both project views, and changes to shared project data appear in both automatically.
- Food recommendations load from a local snapshot, do not display an update date, and can be refreshed without editing map code.
- The site remains usable on a phone and does not load all scene assets on first view.
- Auto lighting follows the specified local-hour ranges without requesting location; manual choices persist when storage is available.
- All three lighting modes preserve readable content and share the same base artwork; reduced-motion users can switch modes without animated transitions.
- Stadium shots can be aimed anywhere within the goal using pointer/touch or keyboard arrows; resizing preserves the selected target. Hold/release shooting resolves exactly one shot.
- Charge cancellation or leaving the scene never leaves controls stuck; the fifth shot ends the optional round cleanly.
- All selectable players use equal ability, and stadium results never gate portfolio content.
- Airport map, list, filters, and totals share one imported flight dataset; only flown records are displayed.
- Missing flight data produces an honest empty state, and malformed CSV imports cannot replace valid flight history.
- Keyboard users can access route details through the flight list without operating the map.

## Content still needed

- Pokédex Ops repository/demo/write-up URLs, when available, plus any preferred changes to its draft blurb.
- Additional personal-project names, short descriptions, and approved links. These automatically populate both project views.
- Beli profile share URL, if an external profile link is desired.
- Initial selected food recommendations, via export, screenshots, or a written list.
- Flight-history CSV from Muse, reviewed for flown/canceled/uncertain status and stripped of reservation details.
- Optional additional personal details for gym or home scenes. Do not add empty buildings just to fill the map.

## Claude handoff files

The handoff bundle contains these files together:

- **PRD.md:** this readable specification, with relative links to the two source assets.
- **PRD.txt:** the same specification in plain text for reliable file ingestion.
- **avatar_reference.png:** visual reference for the small stylized map character only; do not publish the original photo.
- **resume.pdf:** the selected resume, included as the downloadable site asset and source for contact details.
- **START_HERE.txt:** upload steps and a starter implementation prompt.
- **IMPLEMENTATION_SLICES.md:** ordered implementation slices, completion checklists, and review boundaries.
- **BUILD_PROGRESS.md:** initial progress tracker; update it after each slice.
- **CLAUDE.md:** architecture, autonomy, and quality instructions read by Claude Code.
- **flights_template.csv:** header-only format for Muse’s flight-history output; it contains no flight records.

Recommended build workflow: extract the bundle into the project folder and open that folder in Claude Code. Ask it to read PRD.md, inspect avatar_reference.png, and use resume.pdf as the downloadable asset. For Claude Chat, attach PRD.txt, avatar_reference.png, and resume.pdf separately. The ZIP is for transport and storage.

## Decisions confirmed

- **Layouts:** broad town map on desktop; illustrated vertical village path on phones.
- **Art direction:** hybrid illustrated and pixel-art treatment.
- **Atmosphere:** device-local time-of-day lighting, with Auto / Day / Evening / Night choices; no location request or external time service.
- **Avatar:** should resemble Kushal, guided by the attached photo.
- **Work achievements:** keep them on the resume; no achievement showcases in the map.
- **Resume and contact:** use the attached resume version and its email, phone, LinkedIn, and GitHub details in the facts view.
- **Projects:** a scalable, original gym-badge-style case and a directly accessible All projects tab. Each project has a short blurb and available links. Both views share one content source; Pokédex Ops Skill comes first. Workplace achievements stay in the resume.
- **Food recommendations:** manually refreshed Beli snapshot, with no live integration.
- **Flights:** Muse supplies a CSV for Claude to import into local site data. Airport has Route map and All flights tabs; no live Flighty or email connection is required.
- **Soccer:** Barcelona. Stadium game has Kushal, Messi, Ronaldo, Neymar, Haaland, Mbappé, and Lamine Yamal; equal abilities, free aiming within the goal, hold-to-charge shots, NPC goalkeeper, and optional five-shot rounds.
- **Personal cameos:** Naruto, Iruka, Kakashi, and the ramen-shop owner at the ramen shop; Herobrine hidden behind a corner and vanishing on hover/tap/focus.
- **Restaurant:** Kasama in Chicago, separate from the fictional ramen shop.

## Instructions for the implementation assistant

Treat this PRD, the attached resume, the attached avatar reference, and any additional content Kushal explicitly provides as the source of truth. Do not invent biography, work achievements, links, or personal favorites. Build the map, facts view, and core accessibility before the optional stadium game and cameo polish. Keep the original world art distinct from the small requested fan-art cameos. Keep the site fast, maintainable, and easy to extend.
