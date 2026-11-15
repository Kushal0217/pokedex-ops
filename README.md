# Kushal's website

A playable-portfolio site: a small explorable town built with React, TypeScript and Vite. Static output, no backend.

See `PRD.md` (specification), `IMPLEMENTATION_SLICES.md` (build order) and `BUILD_PROGRESS.md` (current state).

```sh
npm install
npm run dev          # local preview
npm run dev:lan      # same-Wi-Fi phone preview; open the Network URL it prints
npm run build        # type-check and build to dist/
npm run check:build  # confirm no private files reached dist/ and the resume is unchanged
node scripts/check-site.mjs   # behaviour checks + screenshots; needs `npm run preview` running and Playwright available
```

`private/` is git-ignored: keep the avatar reference photo and raw flight sources there.

## Updating content

- **Projects:** add an entry to `src/features/projects/projects.ts`. It appears in both the Badges and All
  projects tabs. Leave `links` empty until a real URL exists.
- **Food favourites:** edit `src/features/food/restaurants.ts`.
- **Profile text:** edit `src/features/profile/profile.ts`.
- **Places on the map:** `src/features/world/places.ts`.

## Flights

The airport reads `src/features/flights/flights.data.json`, which is produced from a reviewed CSV. The site
never reads the CSV itself, and there is no live connection to email, Flighty or a calendar.

1. Save the CSV as `private/flights.csv` (that folder is git-ignored and never built). Columns:
   `date,airline,flight_number,origin_airport,destination_airport,status`, one row per flight leg, ISO dates,
   three-letter IATA codes, status `flown`, `booked`, `canceled` or `uncertain`. Leave out booking references,
   ticket numbers, seats, passenger details and email text.
2. Run `npm run import:flights` and read the report it prints (also saved to
   `private/flights-import-report.txt`). Fix anything it lists under invalid rows, possible duplicates or
   airports without map data, and run it again.
3. Run `npm run build`.

Only `flown` rows are published. If the file is malformed, or would remove all existing flights, the import
stops and the current data is kept (`--allow-empty` overrides the second case).

`npm test` runs the importer's tests on synthetic data. Data sources and licences are in `data/README.md`.
