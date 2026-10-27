import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'

type DashboardEvent = { id: string; category: string; description: string; occurred_at: string; person: string | null }
type DashboardNeed = {
  id: string; name: string; person: 'me' | 'partner'; importance: 'low' | 'medium' | 'high';
  latest_status: 'met' | 'partly_met' | 'not_met' | null; latest_satisfaction: number | null;
  latest_update_on: string | null; low_satisfaction: boolean; stale: boolean;
  trend: 'improving' | 'declining' | 'steady' | 'not_enough_data'
}
type DashboardData = { latest_events: Record<string, DashboardEvent | null>; latest_upset: DashboardEvent | null; recent_events: DashboardEvent[]; needs: DashboardNeed[] }
type AnalysisSettings = { enabled: boolean; timezone: string; available: boolean; model: string }
type Reflection = {
  id: string; period_type: 'daily' | 'weekly' | 'monthly' | 'yearly'; period_start: string; period_end: string;
  score: number | null; confidence: 'low' | 'medium' | 'high'; coverage_days: number; total_days: number;
  events_analyzed: number; need_updates_analyzed: number; data_summary: string; positive_factors: string[];
  friction_factors: string[]; interpretation: string; comparison: string; unresolved_issues: string[];
  suggested_actions: string[]; reflection: string; limitations: string; updated_at: string
}
type Advice = {
  answer: string; considerations: string[]; suggested_actions: string[];
  limitations: string; safety_note: string | null
}

const activityLabels: Record<string, string> = { intimacy: 'Intimacy', kindness: 'Kind gesture', conflict: 'Conflict', outing: 'Outing', alcohol: 'Drinking', childcare: 'Childcare' }
const statusLabels = { met: 'Met', partly_met: 'Partly met', not_met: 'Not met' }

function eventDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

function localDay(daysFromToday = 0) {
  const value = new Date()
  value.setDate(value.getDate() + daysFromToday)
  return new Date(value.getTime() - value.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function inclusiveEnd(value: string) {
  const day = new Date(`${value}T00:00:00`)
  day.setDate(day.getDate() - 1)
  return day.toISOString().slice(0, 10)
}

export default function Dashboard({ partnerName, refreshKey, onLog }: { partnerName: string; refreshKey: number; onLog: () => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [settings, setSettings] = useState<AnalysisSettings | null>(null)
  const [reflections, setReflections] = useState<Reflection[]>([])
  const [loading, setLoading] = useState(true)
  const [aiBusy, setAiBusy] = useState(false)
  const [error, setError] = useState('')
  const [aiNotice, setAiNotice] = useState('')
  const [period, setPeriod] = useState<Reflection['period_type']>('weekly')
  const [anchorDate, setAnchorDate] = useState(localDay(-1))
  const [adviceQuestion, setAdviceQuestion] = useState('')
  const [advice, setAdvice] = useState<Advice | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    Promise.all([api<DashboardData>('/dashboard'), api<AnalysisSettings>('/analysis/settings'), api<Reflection[]>('/reflections?limit=12')])
      .then(([dashboard, analysis, saved]) => { if (active) { setData(dashboard); setSettings(analysis); setReflections(saved) } })
      .catch(err => { if (active) setError((err as Error).message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [refreshKey])

  async function toggleAnalysis(enabled: boolean) {
    if (!settings) return
    setAiBusy(true)
    setError('')
    setAiNotice('')
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
      const updated = await api<AnalysisSettings>('/analysis/settings', { method: 'PUT', body: JSON.stringify({ enabled, timezone }) })
      setSettings(updated)
      if (!enabled) setAdvice(null)
      setAiNotice(enabled ? 'AI relationship analysis enabled.' : 'AI relationship analysis disabled. Saved reflections remain available.')
    } catch (err) { setError((err as Error).message) }
    finally { setAiBusy(false) }
  }

  async function generateReflection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAiBusy(true)
    setError('')
    setAiNotice('')
    try {
      const reflection = await api<Reflection>('/reflections/generate', { method: 'POST', body: JSON.stringify({ period_type: period, anchor_date: anchorDate }) })
      setReflections(current => [reflection, ...current.filter(item => item.id !== reflection.id)])
      setAiNotice(reflection.score === null ? 'Saved a coverage report. More entries are needed for an AI reflection.' : 'Reflection generated.')
    } catch (err) { setError((err as Error).message) }
    finally { setAiBusy(false) }
  }

  async function removeReflection(reflection: Reflection) {
    if (!window.confirm('Delete this saved reflection?')) return
    setAiBusy(true)
    setError('')
    try {
      await api(`/reflections/${reflection.id}`, { method: 'DELETE' })
      setReflections(current => current.filter(item => item.id !== reflection.id))
      setAiNotice('Reflection deleted.')
    } catch (err) { setError((err as Error).message) }
    finally { setAiBusy(false) }
  }

  async function askForAdvice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAiBusy(true)
    setError('')
    setAiNotice('')
    setAdvice(null)
    try {
      const result = await api<Advice>('/analysis/advice', {
        method: 'POST', body: JSON.stringify({ question: adviceQuestion }),
      })
      setAdvice(result)
    } catch (err) { setError((err as Error).message) }
    finally { setAiBusy(false) }
  }

  const attentionNeeds = data?.needs.filter(need => need.low_satisfaction || need.stale) ?? []
  const changingNeeds = data?.needs.filter(need => need.trend === 'improving' || need.trend === 'declining') ?? []

  return <section className="section-block dashboard-section">
    <div className="section-heading"><div><p className="eyebrow">AT A GLANCE</p><h2>Your dashboard</h2></div><button className="primary-button" onClick={onLog}>＋ Log something</button></div>
    {error && <p className="auth-warning" role="alert">{error}</p>}
    {loading ? <p role="status">Loading your dashboard…</p> : data && <>
      <section className="ai-panel" aria-labelledby="ai-reflection-title">
        <div className="ai-panel-heading"><div><p className="eyebrow">PRIVATE AI ANALYSIS</p><h3 id="ai-reflection-title">Relationship reflection</h3></div><label className="analysis-toggle"><input type="checkbox" checked={settings?.enabled ?? false} onChange={event => void toggleAnalysis(event.target.checked)} disabled={aiBusy || (!settings?.available && !settings?.enabled)} /> {settings?.enabled ? 'On' : 'Off'}</label></div>
        {!settings?.available && <p className="auth-warning">AI analysis is not configured on the server yet.</p>}
        <p className="muted">When enabled, all eligible events and need updates in the selected period are sent securely to OpenAI. Missing days remain unknown.</p>
        <p className="save-notice" role="status">{aiNotice}</p>
        {settings?.enabled && settings.available && <form className="reflection-generator" onSubmit={generateReflection}>
          <label>Period<select value={period} onChange={event => setPeriod(event.target.value as Reflection['period_type'])} disabled={aiBusy}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="yearly">Yearly</option></select></label>
          <label>Date within period<input type="date" value={anchorDate} onChange={event => setAnchorDate(event.target.value)} required disabled={aiBusy} /></label>
          <button className="primary-button" disabled={aiBusy}>{aiBusy ? 'Generating…' : 'Generate reflection'}</button>
        </form>}
        {settings?.available && <section className="advice-panel" aria-labelledby="ask-ai-title">
          <div><p className="eyebrow">ONE-TIME PRIVATE QUESTION</p><h4 id="ask-ai-title">Ask for a perspective</h4></div>
          <p className="muted">Your question and up to 30 recent events and 30 need updates are sent to OpenAI. This app does not save the question or answer.</p>
          {!settings.enabled && <p className="auth-warning">Turn on AI analysis above to ask a question.</p>}
          <form onSubmit={askForAdvice}>
            <label>What would you like help thinking through?
              <textarea value={adviceQuestion} onChange={event => setAdviceQuestion(event.target.value)} minLength={3} maxLength={1000} required disabled={aiBusy || !settings.enabled} placeholder="For example: How can I bring up this recurring conflict calmly?" />
            </label>
            <div className="advice-form-footer"><span>{adviceQuestion.length}/1000</span><button className="primary-button" disabled={aiBusy || !settings.enabled || adviceQuestion.trim().length < 3}>{aiBusy ? 'Thinking…' : 'Ask AI'}</button></div>
          </form>
          {advice && <article className="advice-response" aria-live="polite">
            <h4>Perspective</h4><p>{advice.answer}</p>
            {!!advice.considerations.length && <><h4>Things to consider</h4><ul>{advice.considerations.map(item => <li key={item}>{item}</li>)}</ul></>}
            {!!advice.suggested_actions.length && <><h4>Possible next steps</h4><ul>{advice.suggested_actions.map(item => <li key={item}>{item}</li>)}</ul></>}
            {advice.safety_note && <p className="auth-warning"><strong>Safety:</strong> {advice.safety_note}</p>}
            <p className="limitations">{advice.limitations}</p>
          </article>}
        </section>}
        {!reflections.length ? <div className="reflection-empty"><p className="muted">No saved reflections yet.</p></div> : <>
          <article className="latest-reflection">
            <div className="reflection-score"><span>{reflections[0].score ?? '—'}</span><small>{reflections[0].score === null ? 'Not enough data' : 'out of 100'}</small></div>
            <div className="reflection-copy"><p className="eyebrow">{reflections[0].period_type.toUpperCase()} · {reflections[0].period_start} TO {inclusiveEnd(reflections[0].period_end)} · {reflections[0].confidence.toUpperCase()} CONFIDENCE</p><h4>What the data shows</h4><p>{reflections[0].data_summary}</p>{!!reflections[0].positive_factors.length && <><h4>Positive factors</h4><ul>{reflections[0].positive_factors.map(factor => <li key={factor}>{factor}</li>)}</ul></>}{!!reflections[0].friction_factors.length && <><h4>Friction factors</h4><ul>{reflections[0].friction_factors.map(factor => <li key={factor}>{factor}</li>)}</ul></>}<h4>Interpretation</h4><p>{reflections[0].interpretation}</p><h4>Comparison</h4><p>{reflections[0].comparison}</p>{!!reflections[0].unresolved_issues.length && <><h4>Unresolved issues</h4><ul>{reflections[0].unresolved_issues.map(issue => <li key={issue}>{issue}</li>)}</ul></>}<h4>Reflection</h4><p>{reflections[0].reflection}</p>{!!reflections[0].suggested_actions.length && <><h4>Optional next steps</h4><ul>{reflections[0].suggested_actions.map(action => <li key={action}>{action}</li>)}</ul></>}<p className="coverage-note">Coverage: {reflections[0].coverage_days} of {reflections[0].total_days} days · {reflections[0].events_analyzed} events · {reflections[0].need_updates_analyzed} need updates</p><p className="limitations">{reflections[0].limitations}</p></div>
          </article>
          <details className="reflection-history"><summary>Saved reflection history ({reflections.length})</summary><div>{reflections.map(reflection => <article key={reflection.id}><div><strong>{reflection.period_type[0].toUpperCase() + reflection.period_type.slice(1)}</strong><span>{reflection.period_start} to {inclusiveEnd(reflection.period_end)} · {reflection.score ?? 'Not enough data'}</span></div><button className="text-button danger" disabled={aiBusy} onClick={() => void removeReflection(reflection)}>Delete</button></article>)}</div></details>
        </>}
      </section>
      <div className="activity-grid">{Object.entries(activityLabels).map(([category, label]) => {
        const event = data.latest_events[category]
        return <article className="activity-card" key={category}><p className="eyebrow">LAST {label.toUpperCase()}</p>{event ? <><h3>{eventDate(event.occurred_at)}</h3><p>{event.description}</p></> : <p className="muted">No entry recorded</p>}</article>
      })}<article className="activity-card"><p className="eyebrow">LAST TIME SOMEONE WAS UPSET</p>{data.latest_upset ? <><h3>{eventDate(data.latest_upset.occurred_at)}</h3><p>{data.latest_upset.description}</p></> : <p className="muted">No entry recorded</p>}</article></div>

      <div className="dashboard-columns">
        <article className="dashboard-panel"><div className="dashboard-panel-heading"><h3>Current needs</h3><span>{data.needs.length}</span></div>{!data.needs.length ? <p className="muted">No active needs yet.</p> : <ul className="dashboard-need-list">{data.needs.slice(0, 5).map(need => <li key={need.id}><div><strong>{need.name}</strong><span>{need.person === 'me' ? 'For me' : `For ${partnerName}`}</span></div><span>{need.latest_status ? statusLabels[need.latest_status] : 'No update'}</span></li>)}</ul>}</article>
        <article className="dashboard-panel"><div className="dashboard-panel-heading"><h3>Needs attention</h3><span>{attentionNeeds.length}</span></div>{!attentionNeeds.length ? <p className="muted">Nothing is flagged from your recorded updates.</p> : <div className="insight-list">{attentionNeeds.map(need => <p key={need.id}><strong>{need.name}</strong><span>{[need.low_satisfaction ? `Recent satisfaction: ${need.latest_satisfaction}/5` : '', need.stale ? need.latest_update_on ? `No update since ${new Date(`${need.latest_update_on}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' })}` : 'No update recorded' : ''].filter(Boolean).join(' · ')}</span></p>)}</div>}</article>
        <article className="dashboard-panel"><div className="dashboard-panel-heading"><h3>Recent trends</h3><span>{changingNeeds.length}</span></div>{!changingNeeds.length ? <p className="muted">Four updates are needed before a trend appears.</p> : <div className="insight-list">{changingNeeds.map(need => <p key={need.id}><strong>{need.name}</strong><span className={`trend ${need.trend}`}>{need.trend === 'improving' ? 'Trending better' : 'Trending lower'}</span></p>)}</div>}</article>
      </div>

      <article className="recent-summary"><h3>Recent activity</h3>{!data.recent_events.length ? <p className="muted">No entries recorded yet.</p> : <ol>{data.recent_events.map(event => <li key={event.id}><span className="status-pill">{activityLabels[event.category] ?? event.category}</span><div><strong>{event.description}</strong><time dateTime={event.occurred_at}>{eventDate(event.occurred_at)}</time></div></li>)}</ol>}</article>
    </>}
  </section>
}
