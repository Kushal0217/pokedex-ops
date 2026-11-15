# Data sources

| File | What | Source | Licence |
| --- | --- | --- | --- |
| `airports.json` | IATA code to airport name, city, ISO country code, latitude and longitude. Used by `scripts/import-flights.mjs` only; it is not shipped to visitors. | OurAirports `airports.csv`, https://ourairports.com/data/ (retrieved 2026-11-15). Rebuild with `node scripts/build-airport-lookup.mjs airports.csv`. | Public domain |
| `src/features/flights/worldMap.generated.ts` | Simplified world land outline for the route map. | Natural Earth 1:110m land, via the `world-atlas` npm package. Rebuild with `node scripts/build-world-map.mjs`. | Public domain (Natural Earth); package ISC |
