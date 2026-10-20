import { useEffect, useState } from 'react'

type AuthUser = {
  provider: 'google' | 'apple'
  email: string | null
  name: string | null
  pictureUrl: string | null
}

const needs = [
  { name: 'Quality time', detail: '1 of 2 this week', progress: 50, tone: 'terracotta' },
  { name: 'Physical affection', detail: '3 of 3 this week', progress: 100, tone: 'sage' },
]

const quickLog = ['Intimacy', 'Kindness', 'Conflict', 'Outing', 'Alcohol', 'Childcare']

function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(() =>
    new URLSearchParams(window.location.search).has('auth_error')
      ? 'Sign-in could not be completed. Please try again with your original sign-in provider.'
      : null)

  useEffect(() => {
    fetch('/api/auth/me', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Authentication service unavailable')
        return response.json() as Promise<{ user: AuthUser | null }>
      })
      .then(({ user: currentUser }) => setUser(currentUser))
      .catch(() => setAuthError('The sign-in service is not configured yet.'))
      .finally(() => setAuthLoading(false))
  }, [])

  const signIn = (provider: 'google' | 'apple') => {
    window.location.assign(`/api/auth/${provider}/start`)
  }

  const signOut = async () => {
    try {
      const response = await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
      if (!response.ok) throw new Error('Sign-out failed')
      setUser(null)
      setAuthError(null)
    } catch {
      window.alert('Could not sign out. Please try again.')
    }
  }

  if (authLoading) {
    return <main className="auth-shell"><div className="auth-card"><div className="brand-mark">r</div><p className="muted">Opening your private journal…</p></div></main>
  }

  if (!user) {
    return (
      <main className="auth-shell">
        <div className="auth-card">
          <div className="brand-mark" aria-hidden="true">r</div>
          <p className="eyebrow">PRIVATE JOURNAL</p>
          <h1>Our Notes</h1>
          <p className="auth-intro">A quiet place to notice what is happening, remember what matters, and take thoughtful action.</p>
          {authError && <p className="auth-warning" role="status">{authError}</p>}
          <div className="auth-actions">
            <button className="auth-provider-button" onClick={() => signIn('google')}>
              <span className="provider-mark google-mark" aria-hidden="true">G</span>
              Continue with Google
            </button>
            <button className="auth-provider-button dark-provider" onClick={() => signIn('apple')}>
              <span className="provider-mark apple-mark" aria-hidden="true">●</span>
              Continue with Apple
            </button>
          </div>
          <p className="auth-footnote">Your account keeps your journal private. We never need your provider password.</p>
        </div>
      </main>
    )
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">r</div>
        <div>
          <p className="eyebrow">PRIVATE JOURNAL</p>
          <h1>Relationship Tracker</h1>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" aria-label="Toggle color mode">☼</button>
          <button className="icon-button" aria-label="Open settings">⚙</button>
          <button className="avatar-button" onClick={signOut} aria-label="Sign out">
            {user.name?.slice(0, 1).toUpperCase() ?? user.email?.slice(0, 1).toUpperCase() ?? 'U'}
          </button>
        </div>
      </header>

      <section className="welcome-row">
        <div>
          <p className="eyebrow">TODAY</p>
          <h2>Good morning, {user.name?.split(' ')[0] ?? 'there'}</h2>
          <p className="muted">A small place to notice what is happening and what matters.</p>
        </div>
        <button className="primary-button">＋ Log something</button>
      </section>

      <section className="reflection-card" aria-label="Daily reflection preview">
        <div className="reflection-heading">
          <div>
            <p className="eyebrow">DAILY REFLECTION</p>
            <h2>Today’s reflection</h2>
          </div>
          <span className="status-pill">Coming soon</span>
        </div>
        <div className="reflection-body">
          <div className="score-placeholder">—</div>
          <div>
            <p className="muted">Your daily reflection will appear here after you begin logging.</p>
            <p className="reflection-note">The score will always include context, confidence, and an explanation.</p>
          </div>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">QUICK LOG</p>
            <h2>What happened?</h2>
          </div>
        </div>
        <div className="quick-log-grid">
          {quickLog.map((item) => <button className="quick-log-button" key={item}>{item}</button>)}
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RELATIONSHIP NEEDS</p>
            <h2>What matters right now</h2>
          </div>
          <button className="text-button">View all →</button>
        </div>
        <div className="needs-list">
          {needs.map((need) => (
            <article className="need-card" key={need.name}>
              <div className="need-header">
                <div>
                  <h3>{need.name}</h3>
                  <p className="muted">{need.detail}</p>
                </div>
                <span className={`need-dot ${need.tone}`} aria-hidden="true" />
              </div>
              <div className="progress-track" aria-label={`${need.progress}% complete`}>
                <div className={`progress-fill ${need.tone}`} style={{ width: `${need.progress}%` }} />
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section-block activity-block">
        <div className="section-heading">
          <div>
            <p className="eyebrow">RECENT ACTIVITY</p>
            <h2>Your timeline</h2>
          </div>
          <button className="text-button">View timeline →</button>
        </div>
        <div className="empty-state">
          <span className="empty-icon" aria-hidden="true">✦</span>
          <p>Your first entry will start your timeline.</p>
        </div>
      </section>
    </main>
  )
}

export default App
