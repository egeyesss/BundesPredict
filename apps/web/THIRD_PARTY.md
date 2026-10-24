# Third-party code

Components copied into this repo (not installed from npm) and the licence they came with.

| Component | Where | Source | Licence |
|---|---|---|---|
| shadcn/ui primitives (button, input, dialog, sheet, tabs, tooltip, dropdown-menu, sonner, skeleton, avatar, badge, card, chart) | `components/ui/` | https://ui.shadcn.com | MIT |
| OtpInput (sign-in code field) | `components/ui/otp-input.tsx` | https://www.rareui.com/components/otpinput | Free for commercial use with a visible credit link (the footer links to rareui.com) |
| FAQ chat bubbles (grey questions, red answers with the orb avatar) | `components/marketing/Faq.tsx` | https://www.rareui.com | Free for commercial use with a visible credit link (the footer links to rareui.com); rebuilt here with our own tokens and the `motion` package |
| Barlow Condensed Bold (font file for the generated icons and share image) | `assets/fonts/BarlowCondensed-Bold.ttf` | https://github.com/jpt/barlow | SIL Open Font License 1.1 |

The primitives are restyled with the project's design tokens.
Packages they pull in from npm (Radix UI, `cn`, Recharts, Sonner, Lucide) keep their own licences in `node_modules`.

## Brand assets

Club crests in `public/crests/` and the Bundesliga logo are trademarks of their owners.
Each crest's source URL is recorded in `public/crests/manifest.json` and rebuilt from `scripts/crests.json` with `npm run crests:build`.
The logo in `public/crests/league/bundesliga.svg` is the DFL's 2017 Bundesliga logo, taken from https://en.wikipedia.org/wiki/File:Bundesliga_logo_(2017).svg (credited to bundesliga.de).
Unlike the old text-only wordmark it is copyrighted artwork as well as a trademark, and Wikipedia hosts it as non-free content.
It is used unmodified, only to name the competition the data covers, next to the footer's no-affiliation notice, and is removed if the DFL asks.
