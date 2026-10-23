import { createHash } from "node:crypto";

/**
 * Docker volume names for the container's node_modules and .next, unique per checkout and CPU
 * arch, so two worktrees running `npm run e2e` at once never share an install or build cache.
 */
export function volumeNames(repoRoot, arch) {
  const checkout = createHash("sha256").update(repoRoot).digest("hex").slice(0, 10);
  return {
    nodeModules: `bp-web-node-modules-${arch}-${checkout}`,
    nextCache: `bp-web-next-cache-${arch}-${checkout}`,
  };
}
