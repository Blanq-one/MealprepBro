// Draws the app icons as PNGs with no dependencies (node:zlib only): a green tile with a white bowl.
// Output: public/icons/{icon-192,icon-512,maskable-512,apple-touch-icon}.png. Run: npm run icons
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
const GREEN = [47, 111, 78];
const CREAM = [246, 245, 241];
const LEAF = [143, 201, 119];

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function png(size, pixel) {
  const raw = Buffer.alloc((size * 4 + 1) * size);
  for (let y = 0; y < size; y += 1) {
    const row = y * (size * 4 + 1);
    raw[row] = 0; // no filter
    for (let x = 0; x < size; x += 1) {
      const [r, g, b, a] = pixel((x + 0.5) / size, (y + 0.5) / size);
      const i = row + 1 + x * 4;
      raw[i] = r;
      raw[i + 1] = g;
      raw[i + 2] = b;
      raw[i + 3] = a;
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 6; // RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

/** scale < 1 shrinks the drawing toward the centre (maskable icons keep it in the safe zone). */
function bowl(scale, rounded) {
  return (u, v) => {
    if (rounded) {
      const r = 0.2;
      const dx = Math.max(r - u, 0, u - (1 - r));
      const dy = Math.max(r - v, 0, v - (1 - r));
      if (dx * dx + dy * dy > r * r) return [0, 0, 0, 0];
    }
    const x = (u - 0.5) / scale + 0.5;
    const y = (v - 0.5) / scale + 0.5;
    // the bowl: lower half of a circle, with a rim
    const cx = 0.5;
    const cy = 0.48;
    const d = Math.hypot(x - cx, y - cy);
    const inBowl = y >= cy && d <= 0.3;
    const inRim = Math.abs(y - cy) <= 0.025 && Math.abs(x - cx) <= 0.34;
    // a leaf above the rim
    const lx = (x - 0.56) / 0.11;
    const ly = (y - 0.33) / 0.06;
    const inLeaf = lx * lx + ly * ly <= 1 && y < cy - 0.03;
    if (inRim || inBowl) return [...CREAM, 255];
    if (inLeaf) return [...LEAF, 255];
    return [...GREEN, 255];
  };
}

mkdirSync(OUT, { recursive: true });
const icons = {
  "icon-192.png": png(192, bowl(1, true)),
  "icon-512.png": png(512, bowl(1, true)),
  "maskable-512.png": png(512, bowl(0.78, false)),
  "apple-touch-icon.png": png(180, bowl(1, false)), // iOS rounds the corners itself
};
for (const [name, data] of Object.entries(icons)) {
  writeFileSync(join(OUT, name), data);
  console.log(`${name} ${data.length} bytes`);
}
