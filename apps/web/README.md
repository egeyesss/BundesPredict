This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## API client

`lib/api/schema.d.ts` is generated from `apps/backend/openapi.json`; never edit it by hand.
After the backend schema changes, regenerate it with `npm run api:types` (CI fails on a diff).

The Django backend rejects `/api/*` and `/_allauth/*` requests that lack a matching `x-proxy-secret` header.
In dev, both sides default to the same value: the backend uses `PROXY_SECRET` or `dev-only-proxy-secret`, so put `PROXY_SECRET=dev-only-proxy-secret` in `.env.local` and send it as `x-proxy-secret` from server-side fetches and the proxy.
`API_BASE_URL` is the backend origin.

To work without a backend, set `NEXT_PUBLIC_API_MOCKING=enabled` and call `enableApiMocking()` from `lib/api/mocks/browser.ts` before the first render.
In Vitest, call `setupApiMocks()` from `lib/api/mocks/vitest.ts` at the top of a test file.
The mock chat picks a scenario from words in the query: "kane" for the tool-heavy run, "error" for a mid-stream failure, "quota" for the 402, "last chat" for the final free chat.
The recorded streams are regenerated with `uv run python scripts/record_mock_streams.py`.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
