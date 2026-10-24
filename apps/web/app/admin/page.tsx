import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { AdminDashboard } from "@/components/admin/AdminDashboard";
import { loadAdminMetrics, parseRange } from "@/lib/admin/load";
import { loginUrl } from "@/lib/auth/next-path";

export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false } };

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ days?: string | string[] }> }) {
  const range = parseRange((await searchParams).days);
  const outcome = await loadAdminMetrics(range);
  if (outcome.status !== "ok") {
    if (outcome.status === "signed_out") redirect(loginUrl(`/admin?days=${range}`));
    if (outcome.status === "forbidden") notFound();
    throw new Error("Could not load the admin metrics from the API.");
  }
  return <AdminDashboard metrics={outcome.metrics} range={range} />;
}
