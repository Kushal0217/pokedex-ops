// Verifies the production output contains no private inputs. Run after `npm run build`.
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

const walk = (dir) => readdirSync(dir).flatMap((f) => { const p = join(dir, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
const sha = (p) => createHash('sha256').update(readFileSync(p)).digest('hex');

if (!existsSync('dist')) { console.error('dist/ missing: run npm run build first'); process.exit(1); }
const privateHashes = new Set(existsSync('private') ? walk('private').map(sha) : []);
const problems = [];
for (const file of walk('dist')) {
  if (privateHashes.has(sha(file))) problems.push(`${file}: identical to a file in private/`);
  if (/avatar_reference|\.csv$|\.eml$|\.env/i.test(file)) problems.push(`${file}: private-looking file name`);
  // No photo belongs in the build yet; all art is SVG/CSS.
  if (/\.(png|jpe?g|webp|heic)$/i.test(file)) problems.push(`${file}: unexpected raster image`);
}
if (problems.length) { console.error('FAILED\n' + problems.join('\n')); process.exit(1); }
console.log(`OK: ${walk('dist').length} files in dist/, none private (${privateHashes.size} private file(s) compared by hash).`);
