import { appUrl, createSession, googleConfig, sessionCookie, stateMatches, type SessionUser } from './lib/auth'

export default async (request: Request): Promise<Response> => {
  const url = new URL(request.url)
  const code = url.searchParams.get('code')
  const state = url.searchParams.get('state')
  if (!code || !stateMatches(request, state)) return new Response('Invalid Google authentication response', { status: 401 })

  const config = googleConfig(request)
  const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id: config.clientId,
      client_secret: config.clientSecret,
      redirect_uri: config.callbackUrl,
      grant_type: 'authorization_code',
    }),
  })
  if (!tokenResponse.ok) return new Response('Google token exchange failed', { status: 502 })
  const tokens = await tokenResponse.json() as { access_token?: string }
  if (!tokens.access_token) return new Response('Google did not return an access token', { status: 502 })

  const profileResponse = await fetch('https://openidconnect.googleapis.com/v1/userinfo', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  })
  if (!profileResponse.ok) return new Response('Google profile lookup failed', { status: 502 })
  const profile = await profileResponse.json() as { sub?: string; email?: string; name?: string; picture?: string; email_verified?: boolean }
  if (!profile.sub || !profile.email || profile.email_verified === false) return new Response('Google account could not be verified', { status: 401 })

  const user: SessionUser = {
    provider: 'google',
    providerSubject: profile.sub,
    email: profile.email,
    name: profile.name ?? null,
    pictureUrl: profile.picture ?? null,
  }
  const token = await createSession(user)
  return new Response(null, {
    status: 302,
    headers: { Location: appUrl(request), 'Set-Cookie': sessionCookie(token, request), 'Cache-Control': 'no-store' },
  })
}
