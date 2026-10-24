import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/_allauth/", "/accounts/", "/account", "/chat", "/admin", "/demo", "/login"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
