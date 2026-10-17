import { appUrl, clearAuthCookies, revokeSession } from './lib/auth'

export default async (request: Request): Promise<Response> => {
  await revokeSession(request)
  const headers = new Headers({
    Location: appUrl(request),
    'Cache-Control': 'no-store',
  })
  for (const cookie of clearAuthCookies(request)) headers.append('Set-Cookie', cookie)
  return new Response(null, {
    status: 303,
    headers,
  })
}
