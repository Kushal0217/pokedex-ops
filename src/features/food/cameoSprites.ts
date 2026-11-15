import type { SpriteDefinition } from '../world/PixelSprite';

/**
 * Ramen-shop cameo: small original pixel fan art of Naruto, Iruka and Kakashi
 * seated at the counter (seen from behind) and the shop's owner behind it.
 * Drawn from scratch for this site; no official artwork, screenshots, logos or
 * village symbols are used. The cameo stays inside the ramen scene.
 */
const O = '#33241f';
const SKIN = '#e0a988';
const NAVY = '#24345e';

/** Seated back view shared by the three guests: A sleeves, B back, U shoulders, C hips. */
const seatedBody = [
  '.....OUUUUUUUUO.....',
  '...OOUUUUUUUUUUOO...',
  '..OUUUUUUUUUUUUUUO..',
  '..OAABBBBBBBBBBAAO..',
  '..OAAaBBBBBBBBaAAO..',
  '..OAAaBBBRRBBBaAAO..',
  '..OAAaBBBRRBBBaAAO..',
  '..OAAaBBBBBBBBaAAO..',
  '..OAAaBBBBBBBBaAAO..',
  '..OAAOBBBBBBBBOAAO..',
  '...OOOBBBBBBBBOOO...',
  '.....OCCCCCCCCO.....',
  '.....OCCCCCCCCO.....',
  '.....OOOOOOOOOO.....',
];

export const narutoSprite: SpriteDefinition = {
  name: 'Naruto (fan art)',
  palette: { O, S: SKIN, K: NAVY, Y: '#f2c230', y: '#d9a520', A: '#f08a2c', a: '#cf6f1c', B: '#f08a2c', U: '#2c6fb0', R: '#c6452f', C: '#f08a2c' },
  rows: [
    '....O....OO....O....',
    '...OYO..OYYO..OYO...',
    '...OYYOOYYYYOOYYO...',
    '..OYYYYYYYYYYYYYYO..',
    '..OYYYYYYYYYYYYYYO..',
    '.OYYYyYYYYYYYYyYYYO.',
    '..OYYYYYYYYYYYYYYO..',
    '..OKKKKKKKKKKKKKKO..',
    '...OYyYYYYYYYYyYO...',
    '....OOSSSSSSSSOO....',
    ...seatedBody,
  ],
};

const vest = { A: NAVY, a: '#1c2b4e', B: '#5d8a4e', U: '#5d8a4e', R: '#5d8a4e', C: NAVY };

export const irukaSprite: SpriteDefinition = {
  name: 'Iruka (fan art)',
  palette: { O, S: SKIN, K: NAVY, H: '#6b4a35', h: '#523828', ...vest },
  rows: [
    '........OOOO........',
    '.......OHHHHO.......',
    '........OHHO........',
    '.....OOOOKKOOOO.....',
    '....OHHHHHHHHHHO....',
    '...OHHHHHHHHHHHHO...',
    '...OHHhHHHHHHhHHO...',
    '...OKKKKKKKKKKKKO...',
    '...OSHHHHHHHHHHSO...',
    '....OOSSSSSSSSOO....',
    ...seatedBody,
  ],
};

export const kakashiSprite: SpriteDefinition = {
  name: 'Kakashi (fan art)',
  palette: { O, S: SKIN, K: NAVY, G: '#c9ccd6', g: '#a3a7b5', ...vest },
  rows: [
    '.....OO..OO.........',
    '....OGGOOGGO..OO....',
    '....OGGGGGGGOOGGO...',
    '...OGGGGGGGGGGGGO...',
    '...OGGGgGGGGGGgGGO..',
    '...OGGGGGGGGGGGGO...',
    '...OGGgGGGGGGgGGO...',
    '...OKKKKKKKKKKKKO...',
    '...OSGGGGGGGGGGSO...',
    '....OOKKKKKKKKOO....',
    ...seatedBody,
  ],
};

export const ownerSprite: SpriteDefinition = {
  name: 'Ramen-shop owner (fan art)',
  palette: { O, S: SKIN, s: '#c98f6e', E: O, W: '#fbf9f4', w: '#d2cdc3', H: '#7a6a5c' },
  rows: [
    '......OOOOOOOO......',
    '.....OWWWWWWWWO.....',
    '.....OWWWWWWWWO.....',
    '....OOwwwwwwwwOO....',
    '....OHSSSSSSSSHO....',
    '....OSSSSSSSSSSO....',
    '....OSEESSSSEESO....',
    '....OSSSSssSSSSO....',
    '....OSSsSSSSsSSO....',
    '.....OSSSEESSSO.....',
    '.....OOSSSSSSOO.....',
    '...OOWWOSSSSOWWOO...',
    '..OWWWWWOSSOWWWWWO..',
    '..OWWWWWWOOWWWWWWO..',
    ...Array<string>(8).fill('..OWWwWWWWWWWWwWWO..'),
  ],
};
