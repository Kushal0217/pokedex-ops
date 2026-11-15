# Kushal's website

A playable-portfolio site: a small explorable town built with React, TypeScript and Vite. Static output, no backend.

See `PRD.md` (specification), `IMPLEMENTATION_SLICES.md` (build order) and `BUILD_PROGRESS.md` (current state).

```sh
npm install
npm run dev          # local preview
npm run dev:lan      # same-Wi-Fi phone preview; open the Network URL it prints
npm run build        # type-check and build to dist/
npm run check:build  # confirm no private files reached dist/
```

`private/` is git-ignored: keep the avatar reference photo and raw flight sources there.
