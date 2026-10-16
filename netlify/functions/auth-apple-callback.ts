import { appUrl, appleClientSecret, appleConfig, createSession, sessionCookie, stateMatches, verifyAppleIdToken, type SessionUser } from './lib/auth'

export default async (request: Request): Promise<Response> => {
  const form = await request.formData()
  const code = typeof form.get('code') === 'string' ? String(form.get('code')) : null
  const state = typeof form.get('state') === 'string' ? String(form.get('state')) : null
  if (!code || !stateMatches(request, state)) return new Response('Invalid Apple authentication response', { status: 401 })

  const config = appleConfig(request)
  const tokenResponse = await fetch('https://appleid.apple.com/auth/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: config.clientId,
      client_secret: await appleClientSecret(request),
      code,
      grant_type: 'authorization_code',
      redirect_uri: config.callbackUrl,
    }),
  })
  if (!tokenResponse.ok) return new Response('Apple token exchange failed', { status: 502 })
  const tokens = await tokenResponse.json() as { id_token?: string }
  if (!tokens.id_token) return new Response('Apple did not return an identity token', { status: 502 })

  const claims = await verifyAppleIdToken(tokens.id_token, config.clientId)
  if (typeof claims.sub !== 'string') return new Response('Apple account could not be verified', { status: 401 })
  const submittedUser = form.get('user')
  let submittedEmail: string | null = null
  let submittedName: string | null = null
  if (typeof submittedUser === 'string') {
    try {
      const parsed = JSON.parse(submittedUser) as { name?: { firstName?: string; lastName?: string }; email?: string }
      submittedEmail = parsed.email ?? null
      submittedName = [parsed.name?.firstName, parsed.name?.lastName].filter(Boolean).join(' ') || null
    } catch {
      // Apple may omit the optional user payload after the first sign-in.
    }
  }

  const emailClaim = typeof claims.email === 'string' ? claims.email : null
  const emailVerified = claims.email_verified === true || claims.email_verified === 'true'
  if ((!emailClaim && !submittedEmail) || (emailClaim && !emailVerified)) return new Response('A verified Apple email is required', { status: 401 })
  const user: SessionUser = {
    provider: 'apple',
    providerSubject: claims.sub,
    email: emailClaim ?? submittedEmail,
    name: submittedName,
    pictureUrl: null,
  }
  const token = await createSession(user)
  return new Response(null, {
    status: 303,
    headers: { Location: appUrl(request), 'Set-Cookie': sessionCookie(token, request), 'Cache-Control': 'no-store' },
  })
}
