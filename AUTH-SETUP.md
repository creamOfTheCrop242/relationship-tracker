# Custom OAuth setup

Phase 2 uses custom Google and Apple OAuth through Netlify Functions. Netlify Identity is not part of this flow, so provider credentials stay in server-side environment variables.

## Netlify environment variables

Add these variables in the Netlify project settings. Do not put secrets in frontend code or commit a `.env` file.

```text
PUBLIC_APP_URL=https://so-about-us.netlify.app
SESSION_SECRET=<long-random-secret>

GOOGLE_CLIENT_ID=<Google web client ID>
GOOGLE_CLIENT_SECRET=<Google web client secret>
GOOGLE_CALLBACK_URL=https://so-about-us.netlify.app/api/auth/google/callback

APPLE_CLIENT_ID=<Apple Services ID>
APPLE_TEAM_ID=<Apple team ID>
APPLE_KEY_ID=<Apple Sign in with Apple key ID>
APPLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
APPLE_CALLBACK_URL=https://so-about-us.netlify.app/api/auth/apple/callback
```

Generate a session secret locally with:

```bash
openssl rand -base64 32
```

## Google

Create a Google OAuth client with application type **Web application**.

Add this authorized JavaScript origin:

```text
https://so-about-us.netlify.app
```

Add this authorized redirect URI:

```text
https://so-about-us.netlify.app/api/auth/google/callback
```

For local testing through Netlify Dev, use:

```text
http://localhost:8888
http://localhost:8888/api/auth/google/callback
```

## Apple

Create or use an Apple primary App ID with Sign in with Apple enabled. Create a web Services ID and configure it with:

- `so-about-us.netlify.app` as a domain
- `https://so-about-us.netlify.app/api/auth/apple/callback` as a return URL

The Apple private key must remain server-side. The callback uses `form_post`, verifies the returned identity token against Apple’s signing keys, and creates a signed application session.

Apple web authentication should be tested on the deployed HTTPS site. The local development callback may not work unless the local URL is accepted by the Apple configuration.

## Local development

Use Netlify Dev so the frontend and Functions share one origin:

```bash
npx netlify dev
```

The app will be available at `http://localhost:8888`.
