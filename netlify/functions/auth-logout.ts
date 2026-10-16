import { appUrl, clearAuthCookies } from './lib/auth'

export default async (request: Request): Promise<Response> => {
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
