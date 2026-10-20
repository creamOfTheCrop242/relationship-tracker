# FastAPI authentication

Google and Apple OAuth are handled by the Heroku FastAPI backend. The browser uses same-origin `/api/auth/*` URLs on the frontend; Netlify proxies `/api/*` to Heroku. Keep callback URLs on the frontend origin so state and session cookies remain first-party. Do not point provider callbacks directly at Heroku when using the Netlify frontend.

## Heroku configuration

Set these server-side variables on `so-about-us`:

```text
FRONTEND_URL=https://your-site.netlify.app
DATABASE_URL=<provided by Heroku Postgres>
SESSION_SECRET=<long random value>
GOOGLE_CLIENT_ID=<Google web client ID>
GOOGLE_CLIENT_SECRET=<Google web client secret>
GOOGLE_CALLBACK_URL=https://your-site.netlify.app/api/auth/google/callback
APPLE_CLIENT_ID=<Apple Services ID>
APPLE_TEAM_ID=<Apple team ID>
APPLE_KEY_ID=<Apple key ID>
APPLE_PRIVATE_KEY=<Apple private key PEM>
APPLE_CALLBACK_URL=https://your-site.netlify.app/api/auth/apple/callback
```

Register the exact callback URLs with Google and Apple. For Google, also register the frontend origin. Apple requires an HTTPS domain, a Services ID, and Sign in with Apple enabled for its associated App ID. A provider with incomplete configuration returns 503 at its start endpoint.

Deploy the backend before publishing the frontend proxy changes. Existing Netlify sessions do not transfer; users must sign in again. The old Netlify database is not migrated by this change. No journal data has been implemented yet.

## Local development

Run FastAPI on port 8000 and `npm run dev` on port 5173. Vite proxies `/api` to FastAPI. In `backend/.env`, use:

```text
FRONTEND_URL=http://localhost:5173
GOOGLE_CALLBACK_URL=http://localhost:5173/api/auth/google/callback
```

Register that exact callback with Google. Apple requires an HTTPS development origin and matching frontend/callback configuration; plain localhost is unsupported. `backend/.env` overrides root `.env` values, so ensure it does not retain obsolete callback URLs.

## Routes and session behavior

- `GET /api/auth/google/start`, `GET /api/auth/apple/start`: begin sign-in.
- `GET /api/auth/google/callback`, `POST /api/auth/apple/callback`: finish sign-in.
- `GET /api/auth/me`: current user, or `{ "user": null }`.
- `POST /api/auth/logout`: revoke the session; requires an Origin header matching `FRONTEND_URL`.

State is signed, expires after ten minutes, and is bound to the browser and provider. Google also uses PKCE. Both providers' identity tokens are checked for signature, issuer, audience, expiration, and nonce. Apple's state cookie uses Secure/SameSite=None to support its cross-site form POST; application sessions use HttpOnly/SameSite=Lax cookies.

Only token hashes are stored in Postgres. Sessions expire after 30 days and logout deletes the stored session. Database failures never fall back to unsigned or independent sessions. Accounts are identified by provider and subject; matching email addresses do not automatically link providers. Returning Apple users can sign in without a repeated email/name payload.

## Verification

Run the backend test suite as described in `BACKEND-SETUP.md`. Provider HTTP responses are mocked; token validation uses locally signed RSA tokens and session tests use real Postgres. After configuring credentials, verify actual Google and Apple sign-in, refresh, and logout through the live frontend. Tests cannot establish that provider-console settings are correct.
