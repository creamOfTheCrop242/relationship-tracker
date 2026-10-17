import { eq } from 'drizzle-orm'
import { SignJWT, importPKCS8, jwtVerify, createRemoteJWKSet } from 'jose'

import { db } from '../../../db'
import { authAccounts, sessions, users } from '../../../db/schema'

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
  const existingUsers = await db.select().from(users).where(eq(users.email, user.email ?? '')).limit(1)
  const savedUser = existingUsers[0]
    ? (await db.update(users)
        .set({ displayName: user.name, avatarUrl: user.pictureUrl, updatedAt: new Date() })
        .where(eq(users.id, existingUsers[0].id))
        .returning())[0]
    : (await db.insert(users).values({
        email: user.email ?? `${user.providerSubject}@${user.provider}.invalid`,
        displayName: user.name,
        avatarUrl: user.pictureUrl,
      }).returning())[0]

  const existingAccounts = await db.select().from(authAccounts)
    .where(eq(authAccounts.providerSubject, user.providerSubject)).limit(1)
  if (existingAccounts[0]) {
    await db.update(authAccounts)
      .set({ userId: savedUser.id, email: user.email ?? existingAccounts[0].email })
      .where(eq(authAccounts.id, existingAccounts[0].id))
  } else {
    await db.insert(authAccounts).values({
      userId: savedUser.id,
      provider: user.provider,
      providerSubject: user.providerSubject,
      email: user.email ?? savedUser.email,
    })
  }

  const token = randomState()
  await db.insert(sessions).values({
    userId: savedUser.id,
    tokenHash: await hashToken(token),
    expiresAt: new Date(Date.now() + SESSION_MAX_AGE * 1000),
  })
  return token
}

export async function getSession(request: Request): Promise<SessionUser | null> {
  const token = cookieValue(request, SESSION_COOKIE)
  if (!token) return null
  try {
    const rows = await db.select({
      provider: authAccounts.provider,
      providerSubject: authAccounts.providerSubject,
      email: users.email,
      name: users.displayName,
      pictureUrl: users.avatarUrl,
      expiresAt: sessions.expiresAt,
    })
      .from(sessions)
      .innerJoin(users, eq(sessions.userId, users.id))
      .innerJoin(authAccounts, eq(authAccounts.userId, users.id))
      .where(eq(sessions.tokenHash, await hashToken(token)))
      .limit(1)
    const session = rows[0]
    if (!session || session.expiresAt.getTime() <= Date.now()) return null
    if (session.provider !== 'google' && session.provider !== 'apple') return null
    return {
      provider: session.provider,
      providerSubject: session.providerSubject,
      email: session.email,
      name: session.name,
      pictureUrl: session.pictureUrl,
    }
  } catch {
    return null
  }
}

export async function revokeSession(request: Request): Promise<void> {
  const token = cookieValue(request, SESSION_COOKIE)
  if (token) await db.delete(sessions).where(eq(sessions.tokenHash, await hashToken(token)))
}

async function hashToken(value: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value))
  return Buffer.from(digest).toString('base64url')
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
