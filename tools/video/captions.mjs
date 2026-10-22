// Renders the burned-in captions as transparent PNGs (ffmpeg's drawtext breaks Hebrew bidi order),
// and the closing frame (the logo on navy). Run by edit.py: node captions.mjs
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const require = createRequire(path.join(REPO, "frontend", "package.json"));
const { chromium } = require("@playwright/test");

const OUT = path.join(HERE, "out", "captions");
fs.mkdirSync(OUT, { recursive: true });
const captions = JSON.parse(fs.readFileSync(path.join(HERE, "captions.json"), "utf8"));
const font = pathToFileURL(
  path.join(REPO, "frontend", "node_modules", "@fontsource", "ibm-plex-sans-hebrew", "files", "ibm-plex-sans-hebrew-hebrew-600-normal.woff2"),
).href;
const logo = pathToFileURL(path.join(REPO, "frontend", "src", "assets", "compass-logo.png")).href;

const pill = (text, size) => `<!doctype html><meta charset="utf-8"><style>
@font-face{font-family:"Plex";src:url("${font}");font-weight:600}
html,body{margin:0;background:transparent}
body{display:inline-block;padding:0}
#pill{display:inline-block;direction:rtl;font:600 ${size}px/1.25 "Plex",sans-serif;color:#fff;
background:rgba(4,19,43,.82);border-radius:${Math.round(size * 0.9)}px;padding:${Math.round(size * 0.32)}px ${Math.round(size * 0.9)}px;white-space:nowrap}
</style><div id="pill">${text}</div>`;

// pages are files (file:// assets are blocked from about:blank)
const HTML = path.join(OUT, "_html");
fs.mkdirSync(HTML, { recursive: true });
async function open(page, html) {
  const file = path.join(HTML, "page.html");
  fs.writeFileSync(file, html, "utf8");
  await page.goto(pathToFileURL(file).href);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1800, height: 300 }, deviceScaleFactor: 1 });
for (const [key, text] of Object.entries(captions)) {
  const small = key.endsWith("note");
  const name = small ? `scene-${key.replace("note", "").padStart(2, "0")}-note.png` : `scene-${key.padStart(2, "0")}.png`;
  await open(page, pill(text, small ? 22 : 40));
  await page.evaluate(() => document.fonts.ready);
  await page.locator("#pill").screenshot({ path: path.join(OUT, name), omitBackground: true });
}
await page.setViewportSize({ width: 1920, height: 1080 });
await open(page, `<!doctype html><meta charset="utf-8"><body style="margin:0;background:#082350;display:grid;place-items:center;height:1080px"><img src="${logo}" style="max-width:640px;max-height:360px">`);
await page.waitForFunction(() => document.images[0].complete);
await page.screenshot({ path: path.join(OUT, "close.png") });
await browser.close();
fs.rmSync(HTML, { recursive: true, force: true });
console.log("captions rendered:", fs.readdirSync(OUT).length, "files");
