import { useEffect, useState } from 'react'
import { api } from './api'

type DashboardEvent = { id: string; category: string; description: string; occurred_at: string; person: string | null }
type DashboardNeed = {
  id: string; name: string; person: 'me' | 'partner'; importance: 'low' | 'medium' | 'high';
  latest_status: 'met' | 'partly_met' | 'not_met' | null; latest_satisfaction: number | null;
  latest_update_on: string | null; low_satisfaction: boolean; stale: boolean;
  trend: 'improving' | 'declining' | 'steady' | 'not_enough_data'
}
type DashboardData = { latest_events: Record<string, DashboardEvent | null>; latest_upset: DashboardEvent | null; recent_events: DashboardEvent[]; needs: DashboardNeed[] }

const activityLabels: Record<string, string> = { intimacy: 'Intimacy', kindness: 'Kind gesture', conflict: 'Conflict', outing: 'Outing', alcohol: 'Drinking', childcare: 'Childcare' }
const statusLabels = { met: 'Met', partly_met: 'Partly met', not_met: 'Not met' }

function eventDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, { dateStyle: 'medium' })
}

export default function Dashboard({ partnerName, refreshKey, onLog }: { partnerName: string; refreshKey: number; onLog: () => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    api<DashboardData>('/dashboard')
      .then(result => { if (active) setData(result) })
      .catch(err => { if (active) setError((err as Error).message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [refreshKey])

  const attentionNeeds = data?.needs.filter(need => need.low_satisfaction || need.stale) ?? []
  const changingNeeds = data?.needs.filter(need => need.trend === 'improving' || need.trend === 'declining') ?? []

  return <section className="section-block dashboard-section">
    <div className="section-heading"><div><p className="eyebrow">AT A GLANCE</p><h2>Your dashboard</h2></div><button className="primary-button" onClick={onLog}>＋ Log something</button></div>
    {error && <p className="auth-warning" role="alert">{error}</p>}
    {loading ? <p role="status">Loading your dashboard…</p> : data && <>
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
