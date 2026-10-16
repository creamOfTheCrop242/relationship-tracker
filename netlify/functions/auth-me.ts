import { getSession } from './lib/auth'

export default async (request: Request): Promise<Response> => {
  const user = await getSession(request)
  return Response.json({ user }, { headers: { 'Cache-Control': 'no-store' } })
}
