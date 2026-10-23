// Runs Playwright inside the official Playwright image so screenshot baselines
// render identically on macOS, Linux CI and teammates' machines.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";

import { playwrightImage } from "./playwright-image.mjs";
import { volumeNames } from "./volume-names.mjs";

const webRoot = path.resolve(import.meta.dirname, "../..");
const repoRoot = path.resolve(webRoot, "../..");
const playwrightArgs = process.argv.slice(2);

const alreadyInContainer = process.env.CI === "true" || existsSync("/.dockerenv");

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit", cwd: webRoot });
  process.exit(result.status ?? 1);
}

if (alreadyInContainer) {
  run("npx", ["playwright", "test", ...playwrightArgs]);
}

// node_modules and .next live in named volumes (one set per checkout and CPU
// arch) so the container never mixes its Linux native binaries with the host's.
const volumes = volumeNames(repoRoot, process.arch);
const installIfLockfileChanged =
  "(cmp -s package-lock.json node_modules/.lockfile-copy || (npm ci --no-audit --no-fund && cp package-lock.json node_modules/.lockfile-copy))";
const containerScript = [
  installIfLockfileChanged,
  `npx playwright test ${playwrightArgs.map((arg) => `'${arg}'`).join(" ")}`,
].join(" && ");

run("docker", [
  "run",
  "--rm",
  "--init",
  "--ipc=host",
  "-e",
  "CI=true",
  "-v",
  `${repoRoot}:/work`,
  "-v",
  `${volumes.nodeModules}:/work/apps/web/node_modules`,
  "-v",
  `${volumes.nextCache}:/work/apps/web/.next`,
  "-w",
  "/work/apps/web",
  playwrightImage(),
  "bash",
  "-c",
  containerScript,
]);
