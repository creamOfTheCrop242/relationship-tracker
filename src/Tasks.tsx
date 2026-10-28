import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'

type Task = { id: string; title: string; description: string | null; source: 'cadence' | 'ai' | 'manual'; status: 'pending' | 'completed' | 'snoozed' | 'dismissed'; due_at: string; snoozed_until: string | null }
type Settings = { enabled: boolean; reminder_time: string; ai_suggestion_frequency: 'off' | 'daily' | 'weekly' | 'monthly'; completed_task_prompt: boolean; timezone: string }
type PushConfig = { enabled: boolean; public_key: string | null }

function localDate(value = new Date(Date.now() + 3600000).toISOString()) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function applicationKey(value: string) {
  const padding = '='.repeat((4 - value.length % 4) % 4)
  const binary = atob((value + padding).replaceAll('-', '+').replaceAll('_', '/'))
  return Uint8Array.from(binary, character => character.charCodeAt(0))
}

export default function Tasks({ onLog }: { onLog: () => void }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [settings, setSettings] = useState<Settings | null>(null)
  const [pushConfig, setPushConfig] = useState<PushConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Task | null>(null)

  async function load(showLoading = true) {
    if (showLoading) setLoading(true)
    setError('')
    try {
      const [taskRows, preferences, push] = await Promise.all([
        api<Task[]>('/tasks'), api<Settings>('/reminder-settings'), api<PushConfig>('/push/config'),
      ])
      setTasks(taskRows)
      setSettings(preferences)
      setPushConfig(push)
      const params = new URLSearchParams(window.location.search)
      const linkedTask = params.get('task')
      if (linkedTask) {
        params.delete('task')
        window.history.replaceState({}, '', `${window.location.pathname}${params.size ? `?${params}` : ''}`)
        setTimeout(() => document.querySelector<HTMLElement>(`[data-task-id="${CSS.escape(linkedTask)}"]`)?.focus(), 0)
      }
    } catch (err) { setError((err as Error).message) }
    finally { if (showLoading) setLoading(false) }
  }
  useEffect(() => {
    void load()
    const refresh = () => { if (document.visibilityState === 'visible') void load(false) }
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    const interval = window.setInterval(refresh, 30000)
    return () => {
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
      window.clearInterval(interval)
    }
  }, [])

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    setBusy(true); setError('')
    try {
      await api(editing ? `/tasks/${editing.id}` : '/tasks', { method: editing ? 'PUT' : 'POST', body: JSON.stringify({ title: String(data.get('title')).trim(), description: String(data.get('description') ?? '').trim() || null, due_at: new Date(String(data.get('due_at'))).toISOString(), need_id: null }) })
      form.reset()
      setEditing(null)
      setNotice(editing ? 'Task updated.' : 'Task added.')
      await load()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function action(task: Task, name: 'complete' | 'snooze' | 'dismiss' | 'reopen') {
    setBusy(true); setError('')
    const until = name === 'snooze' ? new Date(Date.now() + 86400000).toISOString() : null
    try {
      await api(`/tasks/${task.id}/action`, { method: 'POST', body: JSON.stringify({ action: name, until }) })
      setNotice(name === 'complete' ? 'Task completed.' : name === 'snooze' ? 'Task snoozed for one day.' : name === 'dismiss' ? 'Task dismissed.' : 'Task reopened.')
      await load()
      if (name === 'complete' && settings?.completed_task_prompt && window.confirm('Task completed. Would you like to log what happened?')) onLog()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!settings) return
    setBusy(true); setError('')
    try {
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || settings.timezone
      const updated = { ...settings, timezone }
      await api('/reminder-settings', { method: 'PUT', body: JSON.stringify(updated) })
      setSettings(updated)
      setNotice('Reminder settings saved.')
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function enablePush() {
    if (!pushConfig?.public_key || !('serviceWorker' in navigator) || !('PushManager' in window)) return
    setBusy(true); setError('')
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') throw new Error('Notifications were not allowed in this browser.')
      const registration = await navigator.serviceWorker.getRegistration()
      if (!registration) throw new Error('Install or open the deployed app before enabling device notifications.')
      const subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: applicationKey(pushConfig.public_key) })
      await api('/push/subscriptions', { method: 'POST', body: JSON.stringify(subscription.toJSON()) })
      setNotice('Notifications enabled on this device.')
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  const active = tasks.filter(task => task.status === 'pending' || task.status === 'snoozed')
  const history = tasks.filter(task => task.status === 'completed' || task.status === 'dismissed')
  return <section className="section-block tasks-section">
    <div className="section-heading"><div><p className="eyebrow">THOUGHTFUL ACTIONS</p><h2>Reminders and tasks</h2></div><button type="button" className="text-button" disabled={loading || busy} onClick={() => void load()}>Refresh</button></div>
    <p className="muted">Plan something yourself or let cadence reminders turn unmet check-ins into optional tasks.</p>
    {error && <p className="auth-warning" role="alert">{error}</p>}<p className="save-notice" role="status">{notice}</p>
    <form key={editing?.id ?? 'new'} className="task-create" onSubmit={createTask}><label>Action<input name="title" required maxLength={300} placeholder="Plan a walk together" defaultValue={editing?.title ?? ''} disabled={busy} /></label><label>Due<input name="due_at" type="datetime-local" required defaultValue={localDate(editing?.due_at)} disabled={busy} /></label><label className="task-description">Notes (optional)<input name="description" maxLength={2000} defaultValue={editing?.description ?? ''} disabled={busy} /></label><div className="task-form-actions">{editing && <button type="button" className="text-button" onClick={() => setEditing(null)} disabled={busy}>Cancel edit</button>}<button className="primary-button" disabled={busy}>{editing ? 'Save changes' : 'Add task'}</button></div></form>
    {loading ? <p role="status">Loading tasks…</p> : !active.length ? <div className="empty-state"><span className="empty-icon">✓</span><p>No pending relationship tasks.</p></div> : <div className="task-list">{active.map(task => <article className="task-card" key={task.id} tabIndex={-1} data-task-id={task.id}>
      <div><span className="status-pill">{task.source === 'ai' ? 'AI suggestion' : task.source === 'cadence' ? 'Cadence reminder' : 'Personal task'}</span><time dateTime={task.snoozed_until ?? task.due_at}>{task.status === 'snoozed' ? 'Snoozed until ' : 'Due '}{new Date(task.snoozed_until ?? task.due_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></div>
      <h3>{task.title}</h3>{task.description && <p className="muted">{task.description}</p>}
      <div className="task-actions"><button className="text-button" disabled={busy} onClick={() => { setEditing(task); document.querySelector('.task-create')?.scrollIntoView({ behavior: 'smooth' }) }}>Edit or reschedule</button><button className="text-button" disabled={busy} onClick={() => void action(task, 'complete')}>Complete</button><button className="text-button" disabled={busy} onClick={() => void action(task, 'snooze')}>Snooze 1 day</button><button className="text-button danger" disabled={busy} onClick={() => void action(task, 'dismiss')}>Dismiss</button></div>
    </article>)}</div>}
    {settings && <details className="reminder-settings"><summary>Reminder settings</summary><form onSubmit={saveSettings}>
      <label className="archive-toggle"><input type="checkbox" checked={settings.enabled} onChange={event => setSettings({ ...settings, enabled: event.target.checked })} /> Enable reminders</label>
      <label>Reminder hour<input type="time" step="3600" value={settings.reminder_time.slice(0, 5)} onChange={event => setSettings({ ...settings, reminder_time: `${event.target.value}:00` })} /></label>
      <label>AI suggestions<select value={settings.ai_suggestion_frequency} onChange={event => setSettings({ ...settings, ai_suggestion_frequency: event.target.value as Settings['ai_suggestion_frequency'] })}><option value="off">Off</option><option value="daily">At most daily</option><option value="weekly">At most weekly</option><option value="monthly">At most monthly</option></select></label>
      <p className="muted reminder-timezone">At the reminder hour, OpenAI can create one fresh optional action using your profiles, active needs and requests, recent events, and recent tasks. Existing automatic cadence requests are excluded. Private AI Analysis must also be turned on in the dashboard.</p>
      <label className="archive-toggle"><input type="checkbox" checked={settings.completed_task_prompt} onChange={event => setSettings({ ...settings, completed_task_prompt: event.target.checked })} /> Offer to log completed tasks</label>
      <p className="muted reminder-timezone">Times use this device’s timezone: {settings.timezone}</p>
      <div className="reminder-actions"><button className="primary-button" disabled={busy}>Save settings</button>{pushConfig?.enabled && <button type="button" className="text-button" disabled={busy} onClick={() => void enablePush()}>Enable device notifications</button>}{pushConfig && !pushConfig.enabled && <span className="muted">Device notifications need VAPID keys on the server.</span>}</div>
    </form></details>}
    {!!history.length && <details className="task-history"><summary>Completed and dismissed ({history.length})</summary><div>{history.map(task => <article key={task.id}><span>{task.title}</span><button className="text-button" disabled={busy} onClick={() => void action(task, 'reopen')}>Reopen</button></article>)}</div></details>}
  </section>
}
