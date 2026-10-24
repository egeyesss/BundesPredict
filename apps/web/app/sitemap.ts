import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

const PUBLIC_PATHS = ["", "/matchday", "/track-record", "/how-its-built", "/legal/terms", "/legal/privacy", "/legal/refunds"] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  return PUBLIC_PATHS.map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: path === "/matchday" || path === "/track-record" ? "daily" : "monthly",
    priority: path === "" ? 1 : path === "/matchday" ? 0.9 : 0.6,
  }));
}
