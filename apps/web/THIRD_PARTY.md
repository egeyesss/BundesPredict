# Third-party code

Components copied into this repo (not installed from npm) and the licence they came with.

| Component | Where | Source | Licence |
|---|---|---|---|
| shadcn/ui primitives (button, input, dialog, sheet, tabs, tooltip, dropdown-menu, sonner, skeleton, avatar, badge, card, chart) | `components/ui/` | https://ui.shadcn.com | MIT |
| OtpInput (sign-in code field) | `components/ui/otp-input.tsx` | https://www.rareui.com/components/otpinput | Free for commercial use with a visible credit link (the footer links to rareui.com) |

The primitives are restyled with the project's design tokens.
Packages they pull in from npm (Radix UI, `cn`, Recharts, Sonner, Lucide) keep their own licences in `node_modules`.

## Brand assets

Club crests in `public/crests/` and the Bundesliga wordmark are trademarks of their owners.
Each crest's source URL is recorded in `public/crests/manifest.json` and rebuilt from `scripts/crests.json` with `npm run crests:build`.
The wordmark in `public/crests/league/bundesliga.svg` is https://commons.wikimedia.org/wiki/File:Bundesliga_logo.svg (extracted from a DFL publication, marked public domain and trademarked on Commons) and is used unmodified.
