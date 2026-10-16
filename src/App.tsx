const needs = [
  { name: 'Quality time', detail: '1 of 2 this week', progress: 50, tone: 'terracotta' },
  { name: 'Physical affection', detail: '3 of 3 this week', progress: 100, tone: 'sage' },
]

const quickLog = ['Intimacy', 'Kindness', 'Conflict', 'Outing', 'Alcohol', 'Childcare']

function App() {
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
        </div>
      </header>

      <section className="welcome-row">
        <div>
          <p className="eyebrow">TODAY</p>
          <h2>Good morning, Don</h2>
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
