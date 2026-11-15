/**
 * Renders a pixel-art sprite from rows of single-character palette keys.
 * Colours are CSS custom properties, so sprites re-light with the scene.
 * '.' is transparent.
 */
export interface SpriteDefinition {
  /** Human-readable name used for the accessible label. */
  name: string;
  /** Rows of equal length; each character is a key into `palette`. */
  rows: readonly string[];
  /** Palette key -> CSS colour (normally a `var(--token)`). */
  palette: Readonly<Record<string, string>>;
}

interface Run {
  x: number;
  y: number;
  w: number;
  fill: string;
}

/** Merges equal neighbouring pixels in a row into single rectangles. */
export function spriteRuns(sprite: SpriteDefinition): Run[] {
  const runs: Run[] = [];
  sprite.rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const key = row[x]!;
      let end = x + 1;
      while (end < row.length && row[end] === key) end += 1;
      if (key !== '.') {
        const fill = sprite.palette[key];
        if (!fill) throw new Error(`Sprite "${sprite.name}" uses unknown palette key "${key}"`);
        runs.push({ x, y, w: end - x, fill });
      }
      x = end;
    }
  });
  return runs;
}

export function spriteSize(sprite: SpriteDefinition): { width: number; height: number } {
  return { width: sprite.rows[0]?.length ?? 0, height: sprite.rows.length };
}

/** Sprite as an SVG group, for placing inside a scene. `px` is the size of one sprite pixel. */
export function PixelSpriteGroup({ sprite, x, y, px }: { sprite: SpriteDefinition; x: number; y: number; px: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${px})`} shapeRendering="crispEdges">
      {spriteRuns(sprite).map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.fill} />
      ))}
    </g>
  );
}

/** Stand-alone sprite image. */
export function PixelSprite({ sprite, className, label }: { sprite: SpriteDefinition; className?: string; label?: string }) {
  const { width, height } = spriteSize(sprite);
  return (
    <svg
      className={className}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label ?? sprite.name}
      shapeRendering="crispEdges"
    >
      {spriteRuns(sprite).map((r) => (
        <rect key={`${r.x}-${r.y}`} x={r.x} y={r.y} width={r.w} height={1} fill={r.fill} />
      ))}
    </svg>
  );
}
