import type { NextConfig } from "next";

// /styleguide lives in page.styleguide.tsx, an extension that only exists in
// dev and Vercel preview builds, so production never even builds the route.
const styleguideEnabled =
  process.env.NODE_ENV !== "production" ||
  process.env.VERCEL_ENV === "preview" ||
  process.env.ENABLE_STYLEGUIDE === "1";

const nextConfig: NextConfig = {
  pageExtensions: ["tsx", "ts", "jsx", "js", ...(styleguideEnabled ? ["styleguide.tsx"] : [])],
};

export default nextConfig;
