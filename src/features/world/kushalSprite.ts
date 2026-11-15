import type { SpriteDefinition } from './PixelSprite';

/**
 * Kushal's map sprite (front-facing idle), 16 x 28 sprite pixels.
 * Follows the appearance reference: dark hoodie with the hood up under a black
 * jacket, hands in pockets, light blue jeans, white sneakers. The face is kept
 * deliberately minimal; no facial detail is invented.
 */
export const kushalSprite: SpriteDefinition = {
  name: 'Kushal',
  palette: {
    O: 'var(--spr-outline)',
    H: 'var(--spr-hoodie)',
    h: 'var(--spr-hoodie-lo)',
    J: 'var(--spr-jacket)',
    j: 'var(--spr-jacket-hi)',
    T: 'var(--spr-tee)',
    S: 'var(--spr-skin)',
    s: 'var(--spr-skin-lo)',
    K: 'var(--spr-hair)',
    E: 'var(--spr-outline)',
    B: 'var(--spr-jeans)',
    b: 'var(--spr-jeans-lo)',
    W: 'var(--spr-shoe)',
    w: 'var(--spr-shoe-lo)',
  },
  rows: [
    '......OOOO......',
    '....OOHHHHOO....',
    '...OHHHHHHHHO...',
    '..OHHHKKKKHHHO..',
    '..OHHKKKKKKHhO..',
    '..OHHSSSSSSHhO..',
    '..OHHSESSESHhO..',
    '..OHHSSSSSSHhO..',
    '..OhHsSSSSsHhO..',
    '...OhHssssHhO...',
    '..OJJhHTTHhJJO..',
    '.OJjJJhTThJJJJO.',
    '.OJjJJJTTJJJJJO.',
    '.OJjJJJTTJJJJJO.',
    '.OJjJJJHHJJJJJO.',
    '.OJjJJJHHJJJJJO.',
    '.OJJJJJHHJJJJJO.',
    '..OJJJJHHJJJJO..',
    '..OOBBBBBBBBOO..',
    '...OBBBBBBBbO...',
    '...OBBBbbBBbO...',
    '...OBBBOOBBbO...',
    '...OBBbOOBBbO...',
    '...OBBbOOBBbO...',
    '...OBBbOOBBbO...',
    '..OWWWWOOWWWWO..',
    '..OWWWwOOWWWwO..',
    '..OOOOOOOOOOOO..',
  ],
};
