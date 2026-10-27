import { useEffect, useState } from 'react'
import Journal from './Journal'

type AuthUser = { email: string | null; name: string | null }

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(() => new URLSearchParams(window.location.search).has('auth_error') ? 'Sign-in could not be completed. Please try again with your original sign-in provider.' : null)
  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(async response => { if (!response.ok) throw new Error('Sign-in service unavailable. Please refresh and try again.'); return response.json() })
      .then(data => setUser(data.user))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])
  async function signOut() {
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
      if (!response.ok) throw new Error('Could not sign out. Please try again.')
      setUser(null)
      setError(null)
    } catch (err) { window.alert((err as Error).message) }
  }
  if (loading) return <main className="auth-shell"><p role="status">Opening your private journal…</p></main>
  if (user) return <Journal name={user.name?.split(' ')[0] ?? 'there'} signOut={() => void signOut()} onAccountDeleted={() => { setUser(null); setError(null) }} />
  return <main className="auth-shell"><div className="auth-card">
    <div className="brand-mark" aria-hidden="true">r</div><p className="eyebrow">PRIVATE JOURNAL</p><h1>Our Notes</h1>
    <p className="auth-intro">A quiet place to notice what is happening, remember what matters, and take thoughtful action.</p>
    {error && <p className="auth-warning" role="alert">{error}</p>}
    <div className="auth-actions">
      <button className="auth-provider-button" onClick={() => window.location.assign('/api/auth/google/start')}><span className="provider-mark google-mark" aria-hidden="true">G</span>Continue with Google</button>
      <button className="auth-provider-button dark-provider" onClick={() => window.location.assign('/api/auth/apple/start')}><span className="provider-mark apple-mark" aria-hidden="true">●</span>Continue with Apple</button>
    </div><p className="auth-footnote">Your account keeps your journal private. We never need your provider password.</p>
  </div></main>
}
