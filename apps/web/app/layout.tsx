import type { Metadata, Viewport } from "next";
import { Barlow_Condensed, Inter, JetBrains_Mono } from "next/font/google";

import { SessionProvider } from "@/components/account/SessionProvider";
import { AppShell } from "@/components/brand/AppShell";
import { ApiMockingGate } from "@/components/dev/ApiMockingGate";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

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

export const metadata: Metadata = {
  title: "BundesPredict",
  description:
    "Calibrated Bundesliga match predictor with an LLM context-adjustment layer.",
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
              <AppShell>{children}</AppShell>
            </TooltipProvider>
          </SessionProvider>
          <Toaster />
        </ApiMockingGate>
      </body>
    </html>
  );
}
