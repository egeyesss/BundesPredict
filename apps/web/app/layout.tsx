import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Inter, JetBrains_Mono } from "next/font/google";

import { SessionProvider } from "@/components/account/SessionProvider";
import { AppShell } from "@/components/brand/AppShell";
import { DeferredSurface } from "@/components/signature/DeferredSurface";
import { ApiMockingGate } from "@/components/dev/ApiMockingGate";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { SITE_URL } from "@/lib/site";

import "./globals.css";

const display = Barlow_Condensed({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-display",
  fallback: ["Arial Narrow", "sans-serif"],
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

const DESCRIPTION =
  "Win, draw and loss probabilities for every Bundesliga fixture from a calibrated model, with an agent that adjusts them for the news.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "BundesPredict", template: "%s | BundesPredict" },
  description: DESCRIPTION,
  applicationName: "BundesPredict",
  openGraph: { type: "website", siteName: "BundesPredict", locale: "en_CA" },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#0A0A0B",
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${display.variable} ${sans.variable} ${mono.variable}`}
    >
      <body>
        <ApiMockingGate>
          <SessionProvider>
            <TooltipProvider>
              <DeferredSurface>
                <AppShell>{children}</AppShell>
              </DeferredSurface>
            </TooltipProvider>
          </SessionProvider>
          <Toaster />
        </ApiMockingGate>
      </body>
    </html>
  );
}
