// Fails when a production build (made without ENABLE_STYLEGUIDE) still contains the styleguide route.
import { readFileSync } from "node:fs";
import path from "node:path";

const manifestPath = path.resolve(import.meta.dirname, "../../.next/server/app-paths-manifest.json");
const routes = Object.keys(JSON.parse(readFileSync(manifestPath, "utf8")));
const leaked = routes.filter((route) => route.startsWith("/styleguide"));

if (leaked.length > 0) {
  console.error(`Production build contains ${leaked.join(", ")}`);
  process.exit(1);
}
console.log(`Production build has no styleguide route (${routes.length} app routes checked)`);
