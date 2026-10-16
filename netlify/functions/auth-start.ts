import { appUrl, appleConfig, googleConfig, randomState, stateCookie, type Provider } from './lib/auth'

export default async (request: Request): Promise<Response> => {
  const provider = new URL(request.url).searchParams.get('provider') as Provider | null
  if (provider !== 'google' && provider !== 'apple') return new Response('Unsupported provider', { status: 400 })

  const state = randomState()
  const config = provider === 'google' ? googleConfig(request) : appleConfig(request)
  const params = provider === 'google'
    ? new URLSearchParams({
        client_id: config.clientId,
        redirect_uri: config.callbackUrl,
        response_type: 'code',
        scope: 'openid email profile',
        state,
        prompt: 'select_account',
      })
    : new URLSearchParams({
        client_id: config.clientId,
        redirect_uri: config.callbackUrl,
        response_type: 'code',
        response_mode: 'form_post',
        scope: 'name email',
        state,
      })

  const authorizationUrl = provider === 'google'
    ? `https://accounts.google.com/o/oauth2/v2/auth?${params}`
    : `https://appleid.apple.com/auth/authorize?${params}`

  return new Response(null, {
    status: 302,
    headers: {
      Location: authorizationUrl,
      'Set-Cookie': stateCookie(state, request),
      'Cache-Control': 'no-store',
    },
  })
}
