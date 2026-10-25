# Winner Signal deployment

## Topology

- Public frontend: https://winner-signal.vercel.app (Vercel project `winner-signal`, root `apps/web`).
- API: https://winner-signal-api.fly.dev (Fly personal organization, San Jose).
- One shared-CPU machine, 1 GB RAM; API and worker supervised together.
- Encrypted 3 GB `winner_data` volume at `/data`, with Fly scheduled snapshots enabled.
- Fresh production database: local accounts, recordings and session histories are not copied.
- Gemini configuration is injected as Fly secrets; the key is never sent to Vercel or the browser.
- HTTPS cookies, exact public Origin check, no-store API responses.
- Eight live review attempts per UTC day across the whole app, including failed attempts. Existing queued jobs remain idempotent. Per-attempt model cost checks remain enabled.

## Deploy again

From the repository root:

```sh
fly deploy --remote-only --ha=false --app winner-signal-api
vercel deploy --prod --yes --scope fretin13-9865s-projects
```

The Vercel project has `API_INTERNAL_URL=https://winner-signal-api.fly.dev` configured for production. The Next.js external rewrite keeps API cookies on the frontend origin. Large upload and video range requests must be tested through this rewrite after routing changes.

Never increase the backend to multiple machines without migrating SQLite and filesystem artifacts to shared durable services. Do not run a second worker against another copy of the data. Machine restarts preserve the volume; interrupted reviews are marked failed and can be retried explicitly.

## Scope and operations

This is a public beta with a single backend machine, not a highly available service. Fly compute/volume and model usage may incur charges under the existing accounts. Current disk capacity is 3 GB; monitor it before inviting a large cohort. Scheduled volume snapshots are enabled, but a restore drill has not yet been performed.

The app has no password recovery or email verification yet. Imported video-host reports remain owner-supplied reports, not OAuth-verified host analytics. Private fixture/test projects are not published to the discovery gallery.

Use `fly status -a winner-signal-api`, `fly checks list -a winner-signal-api`, and `fly logs -a winner-signal-api` for service health. Avoid logging submitted histories, model prompts, passwords or API keys.

## Verification

Deployment verification results are recorded in `STATUS.md`; local diagnostic receipts are git-ignored under `data/`.

## Google and YouTube OAuth setup

A separate Google Cloud project `winner-signal-2026` (number `403095482858`) was created for Winner Signal. YouTube Data API v3 and YouTube Analytics API are enabled. No EasyCircuit credentials are reused.

Implemented web-client callbacks (register both in Google Console):

- Sign-in: `https://winner-signal.vercel.app/api/auth/google/callback`
- Optional YouTube connection: `https://winner-signal.vercel.app/api/integrations/youtube/callback`

Google sign-in requests OpenID/email/profile plus optional read-only YouTube scopes with offline access. If the user grants both YouTube scopes and a refresh token is returned, the callback connects their channel automatically. Missing permission, no channel or a channel API failure does not prevent sign-in. Existing uploader connections are preserved on subsequent sign-ins. The optional YouTube connection selects a potentially different account and requests `youtube.readonly` plus `yt-analytics.readonly` with offline access. Tokens are encrypted with `OAUTH_TOKEN_ENCRYPTION_KEY`, separate from app sessions. A channel mismatch prevents report fetching but never blocks adding a demo by URL/upload. The dashboard fetches reports on opening and caches each report for six hours; there is no unattended scheduler. Report data is private, channel-bound and separate from manual imports and first-party events. Disconnect deletes the local refresh token and fetched reports. Google account permissions can also be revoked in the user’s Google account.

The separate `winner-signal` OAuth web client is created and its client ID/secret are installed as Fly secrets. Both production callbacks above are saved. The consent application remains External / Testing; the initial owner account is an added test user. Production status reports `configured:true`. Google sign-in now includes optional YouTube scopes; a separate connect/switch action supports a different uploader account. Keep the OAuth application in testing until consent, token handling and video ownership checks have been verified.

Before wider onboarding, complete branding and any required Google verification/publishing. Additional YouTube uploader accounts must be added as test users while in Testing. Credentials are stored locally in ignored, owner-readable files and in backend secrets; never put the client secret in frontend environment variables.
