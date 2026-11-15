# Claude project instructions

Read PRD.md, IMPLEMENTATION_SLICES.md, and BUILD_PROGRESS.md before working.

## Build architecture

Use React + TypeScript + Vite, CSS and original SVG/layered art, GSAP for coordinated site animations, Radix for accessible dialogs/tabs, and lazy-loaded Phaser for the stadium. Keep typed project, restaurant, and imported flight data separate from presentation. Static production output; no backend or runtime account connection.

## Autonomy

Start with Slice 1 only. Complete its quality checks and provide a working desktop/phone preview, then pause for the initial visual-direction review.

After Kushal approves that sample, progress through Slices 2–9 automatically in order. Each slice is a quality checkpoint, not an approval gate. Check real behavior, inspect layouts when browser tools are available, fix issues, update BUILD_PROGRESS.md, and continue. Do not ask routine implementation questions. Record reasonable assumptions and make choices consistent with the PRD.

Missing project URLs, food data, or flights must not stop independent work. Use the PRD’s approved content and explicit empty states. Never invent personal facts, metrics, links, travel, reviews, or ratings.

Ask only for genuinely blocking choices that materially change agreed scope, sensitive external access, or irreversible actions. Do not deploy, publish, buy assets, connect accounts, or scan email without a separate instruction.

At usage/session interruption, save a concise checkpoint with exact current slice, changes completed, check results, remaining issues, and next action. Do not claim background work continues after execution stops.

## Source assets

avatar_reference.png is a private art reference. Do not copy it into public or deployable assets. resume.pdf is the selected downloadable resume and may be included in public output unchanged. flights_template.csv has headers only; real flight history is pending. Raw future CSV/email sources stay outside public assets.

## Quality

Do not mark a slice complete with failed required checks or a placeholder for its core interaction. When a tool/check is unavailable, report that limitation and exact review steps. Keep the town usable with keyboard, phone touch, and reduced motion. Validate production output contains no private reference photo, raw travel sources, credentials, or fake data.

