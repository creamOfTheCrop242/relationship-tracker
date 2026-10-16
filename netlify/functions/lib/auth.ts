import { SignJWT, importPKCS8, jwtVerify, createRemoteJWKSet } from 'jose'

export type Provider = 'google' | 'apple'

export interface SessionUser {
  provider: Provider
  providerSubject: string
  email: string | null
  name: string | null
  pictureUrl: string | null
}

const SESSION_COOKIE = 'relationship_session'
const STATE_COOKIE = 'relationship_oauth_state'
const SESSION_MAX_AGE = 60 * 60 * 24 * 30

function requiredEnv(name: string): string {
  const value = process.env[name]
  if (!value) throw new Error(`Missing required environment variable: ${name}`)
  return value
}

export function appUrl(request: Request): string {
  const requestUrl = new URL(request.url)
  if (requestUrl.hostname === 'localhost' || requestUrl.hostname === '127.0.0.1') {
    return requestUrl.origin
  }
  return process.env.PUBLIC_APP_URL ?? requestUrl.origin
}

function callbackUrl(request: Request, path: string, configuredUrl: string | undefined): string {
  const requestUrl = new URL(request.url)
  if (requestUrl.hostname === 'localhost' || requestUrl.hostname === '127.0.0.1') {
    return `${requestUrl.origin}${path}`
  }
  return configuredUrl ?? `${appUrl(request)}${path}`
}

export function isSecure(request: Request): boolean {
  return new URL(request.url).protocol === 'https:' || appUrl(request).startsWith('https:')
}

export function cookieValue(request: Request, name: string): string | null {
  const header = request.headers.get('cookie') ?? ''
  const item = header.split(';').map((part) => part.trim()).find((part) => part.startsWith(`${name}=`))
  return item ? decodeURIComponent(item.slice(name.length + 1)) : null
}

export function cookieHeader(name: string, value: string, request: Request, maxAge: number): string {
  const secure = isSecure(request) ? '; Secure' : ''
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure}`
}

export function expiredCookie(name: string, request: Request): string {
  const secure = isSecure(request) ? '; Secure' : ''
  return `${name}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${secure}`
}

export function randomState(): string {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  return Buffer.from(bytes).toString('base64url')
}

export async function createSession(user: SessionUser): Promise<string> {
  const secret = new TextEncoder().encode(requiredEnv('SESSION_SECRET'))
  return new SignJWT({ ...user })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(`${SESSION_MAX_AGE}s`)
    .sign(secret)
}

export async function getSession(request: Request): Promise<SessionUser | null> {
  const token = cookieValue(request, SESSION_COOKIE)
  if (!token) return null
  try {
    const secret = new TextEncoder().encode(requiredEnv('SESSION_SECRET'))
    const { payload } = await jwtVerify(token, secret)
    if (payload.provider !== 'google' && payload.provider !== 'apple') return null
    return {
      provider: payload.provider,
      providerSubject: String(payload.providerSubject),
      email: typeof payload.email === 'string' ? payload.email : null,
      name: typeof payload.name === 'string' ? payload.name : null,
      pictureUrl: typeof payload.pictureUrl === 'string' ? payload.pictureUrl : null,
    }
  } catch {
    return null
  }
}

export function sessionCookie(token: string, request: Request): string {
  return cookieHeader(SESSION_COOKIE, token, request, SESSION_MAX_AGE)
}

export function stateCookie(state: string, request: Request): string {
  return cookieHeader(STATE_COOKIE, state, request, 600)
}

export function clearAuthCookies(request: Request): string[] {
  return [expiredCookie(SESSION_COOKIE, request), expiredCookie(STATE_COOKIE, request)]
}

export function stateMatches(request: Request, returnedState: string | null): boolean {
  const expectedState = cookieValue(request, STATE_COOKIE)
  return Boolean(expectedState && returnedState && expectedState === returnedState)
}

export function googleConfig(request: Request) {
  return {
    clientId: requiredEnv('GOOGLE_CLIENT_ID'),
    clientSecret: requiredEnv('GOOGLE_CLIENT_SECRET'),
    callbackUrl: callbackUrl(request, '/api/auth/google/callback', process.env.GOOGLE_CALLBACK_URL),
  }
}

export function appleConfig(request: Request) {
  return {
    clientId: requiredEnv('APPLE_CLIENT_ID'),
    teamId: requiredEnv('APPLE_TEAM_ID'),
    keyId: requiredEnv('APPLE_KEY_ID'),
    privateKey: requiredEnv('APPLE_PRIVATE_KEY').replace(/\\n/g, '\n'),
    callbackUrl: callbackUrl(request, '/api/auth/apple/callback', process.env.APPLE_CALLBACK_URL),
  }
}

export async function appleClientSecret(request: Request): Promise<string> {
  const config = appleConfig(request)
  const key = await importPKCS8(config.privateKey, 'ES256')
  return new SignJWT({})
    .setProtectedHeader({ alg: 'ES256', kid: config.keyId })
    .setIssuer(config.teamId)
    .setSubject(config.clientId)
    .setAudience('https://appleid.apple.com')
    .setIssuedAt()
    .setExpirationTime('180d')
    .sign(key)
}

export async function verifyAppleIdToken(idToken: string, clientId: string): Promise<Record<string, unknown>> {
  const appleKeys = createRemoteJWKSet(new URL('https://appleid.apple.com/auth/keys'))
  const verified = await jwtVerify(idToken, appleKeys, {
    issuer: 'https://appleid.apple.com',
    audience: clientId,
  })
  return verified.payload
}

export { SESSION_COOKIE, STATE_COOKIE }
