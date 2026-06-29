import { cpSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");

mkdirSync(dist, { recursive: true });
cpSync(resolve(root, "icons"), resolve(dist, "icons"), { recursive: true });

const manifest = JSON.parse(readFileSync(resolve(root, "manifest.json"), "utf8"));
manifest.action.default_popup = "popup.html";
manifest.icons = {
  "16": "icons/icon-16.png",
  "48": "icons/icon-48.png",
  "128": "icons/icon-128.png",
};
writeFileSync(resolve(dist, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
