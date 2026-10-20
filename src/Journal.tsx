import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

const categories = { intimacy: 'Intimacy', kindness: 'Kindness', conflict: 'Conflict', outing: 'Outing', alcohol: 'Alcohol', childcare: 'Childcare', custom: 'Custom' }
type Category = keyof typeof categories
type Entry = { id: string; category: Category; description: string; occurred_at: string; person: string | null; mood: string | null; impact: string | null; notes: string | null }
type Relationship = { id: string; partner_name: string }

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, { credentials: 'include', ...options, headers: { 'Content-Type': 'application/json', ...options?.headers } })
  if (!response.ok) {
    if (response.status === 401) throw new Error('Your session has expired. Please sign out and sign in again.')
    throw new Error(response.status === 422 ? 'Please check the entry fields and try again.' : 'Could not complete the request. Please try again.')
  }
  return response.status === 204 ? undefined as T : response.json()
}

function localDate(value = new Date().toISOString()) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

export default function Journal({ name, signOut }: { name: string; signOut: () => void }) {
  const [relationship, setRelationship] = useState<Relationship | null>(null)
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [hasMore, setHasMore] = useState(false)
  const [editing, setEditing] = useState<Entry | null>(null)
  const [category, setCategory] = useState<Category>('kindness')
  const [partner, setPartner] = useState('')
  const [formError, setFormError] = useState('')
  const [formVersion, setFormVersion] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [rel, rows] = await Promise.all([api<Relationship | null>('/relationship'), api<Entry[]>('/events?limit=50')])
      setRelationship(rel)
      setPartner(rel?.partner_name === 'Partner' ? '' : rel?.partner_name ?? '')
      setEntries(rows)
      setHasMore(rows.length === 50)
    } catch (err) { setError((err as Error).message) }
    finally { setLoading(false) }
  }
  useEffect(() => { void load() }, [])

  function openForm(selected: Category, entry: Entry | null = null) {
    setEditing(entry)
    setFormVersion(version => version + 1)
    setCategory(selected)
    setFormError('')
    setNotice('')
    dialog.current?.showModal()
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const optional = (key: string) => String(data.get(key) ?? '').trim() || null
    setBusy(true)
    setFormError('')
    try {
      const body = { category, description: String(data.get('description')).trim(), occurred_at: new Date(String(data.get('occurred_at'))).toISOString(), person: optional('person'), mood: optional('mood'), impact: optional('impact'), notes: optional('notes') }
      await api(editing ? `/events/${editing.id}` : '/events', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) })
      dialog.current?.close()
      setNotice(editing ? 'Entry updated.' : 'Entry saved.')
      await load()
    } catch (err) { setFormError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function savePartner(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const rel = await api<Relationship>('/relationship', { method: 'PUT', body: JSON.stringify({ partner_name: partner.trim() || 'Partner' }) })
      setRelationship(rel)
      setNotice('Partner name saved.')
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function remove(entry: Entry) {
    if (!window.confirm('Delete this entry? This cannot be undone.')) return
    setBusy(true)
    setError('')
    try {
      await api(`/events/${entry.id}`, { method: 'DELETE' })
      setNotice('Entry deleted.')
      await load()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function loadMore() {
    setBusy(true)
    setError('')
    try {
      const rows = await api<Entry[]>(`/events?limit=50&offset=${entries.length}`)
      setEntries(previous => [...previous, ...rows.filter(row => !previous.some(item => item.id === row.id))])
      setHasMore(rows.length === 50)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  return <main className="app-shell">
    <header className="topbar">
      <div className="brand-mark" aria-hidden="true">r</div>
      <div><p className="eyebrow">PRIVATE JOURNAL</p><h1>Our Notes</h1></div>
      <button className="text-button" onClick={signOut} disabled={busy}>Sign out</button>
    </header>
    <section className="welcome-row">
      <div><p className="eyebrow">YOU AND {(relationship?.partner_name ?? 'Partner').toUpperCase()}</p><h2>Welcome, {name}</h2><p className="muted">Notice what happened. Remember what matters.</p></div>
      <button className="primary-button" disabled={loading || busy} onClick={() => openForm('kindness')}>＋ Log something</button>
    </section>
    {error && <div className="auth-warning" role="alert">{error} <button className="text-button" disabled={busy || loading} onClick={() => void load()}>Retry</button></div>}
    <p className="save-notice" role="status">{notice}</p>
    <details className="partner-settings"><summary>Partner name (optional)</summary>
      <form onSubmit={savePartner} className="partner-form"><label>What would you like to call your partner?<input value={partner} onChange={e => setPartner(e.target.value)} placeholder="Partner" maxLength={100} disabled={loading || busy} /></label><button className="primary-button" disabled={loading || busy}>Save name</button></form>
      <p className="muted">This journal is private to you. Adding a name does not invite or notify anyone.</p>
    </details>
    <section className="section-block"><div className="section-heading"><h2>What happened?</h2></div>
      <div className="quick-log-grid">{Object.entries(categories).map(([value, label]) => <button key={value} className="quick-log-button" disabled={loading || busy} onClick={() => openForm(value as Category)}>{label}</button>)}</div>
    </section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Your timeline</h2></div></div>
      {loading ? <p role="status">Loading your entries…</p> : !entries.length && !error ? <div className="empty-state"><span className="empty-icon">✦</span><p>Your first entry will start your timeline.</p></div> : <div className="timeline">{entries.map(entry => <article className="entry-card" key={entry.id}>
        <div className="entry-meta"><span className="status-pill">{categories[entry.category]}</span><time dateTime={entry.occurred_at}>{new Date(entry.occurred_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></div>
        <h3>{entry.description}</h3>
        {entry.person && <p className="muted">Involved: {entry.person === 'partner' ? relationship?.partner_name ?? 'Partner' : entry.person}</p>}
        {entry.mood && <p>Mood: {entry.mood}</p>}{entry.impact && <p>Impact: {entry.impact}</p>}
        {entry.notes && <p className="entry-notes">{entry.notes}</p>}
        <div className="entry-actions"><button className="text-button" disabled={busy} onClick={() => openForm(entry.category, entry)}>Edit<span className="sr-only"> {entry.description}</span></button><button className="text-button danger" disabled={busy} onClick={() => void remove(entry)}>Delete<span className="sr-only"> {entry.description}</span></button></div>
      </article>)}</div>}
      {hasMore && !loading && <button className="primary-button load-more" disabled={busy} onClick={() => void loadMore()}>{busy ? 'Loading…' : 'Load older entries'}</button>}
    </section>
    <section className="reflection-card"><p className="eyebrow">COMING SOON</p><h3>Relationship needs and reflections</h3><p className="muted">For now, start with the moments you want to remember.</p></section>
    <dialog ref={dialog} className="entry-dialog" aria-labelledby="entry-title" onCancel={event => { if (busy) event.preventDefault() }}>
      <form key={formVersion} onSubmit={save}>
        <h2 id="entry-title">{editing ? 'Edit entry' : 'Log a moment'}</h2>
        <p className="muted">A few words are enough. All times are in your device’s timezone.</p>
        {formError && <p className="auth-warning" role="alert">{formError}</p>}
        <fieldset disabled={busy}>
          <label>Category<select value={category} onChange={e => setCategory(e.target.value as Category)}>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          <label>When<input name="occurred_at" type="datetime-local" required defaultValue={localDate(editing?.occurred_at)} /></label>
          <label>What happened?<input name="description" required maxLength={500} defaultValue={editing?.description ?? ''} placeholder="A walk together, a kind word, a difficult conversation…" /></label>
          <label>Who was involved? (optional)<select name="person" defaultValue={editing?.person ?? ''}><option value="">Not specified</option><option value="me">Me</option><option value="partner">{relationship?.partner_name ?? 'Partner'}</option><option value="both">Both</option><option value="neither">Neither</option></select></label>
          <label>Mood (optional)<input name="mood" maxLength={100} defaultValue={editing?.mood ?? ''} /></label>
          <label>Impact (optional)<input name="impact" maxLength={200} defaultValue={editing?.impact ?? ''} /></label>
          <label>Notes (optional)<textarea name="notes" rows={4} maxLength={10000} defaultValue={editing?.notes ?? ''} /></label>
        </fieldset>
        <div className="form-actions"><button type="button" className="text-button" disabled={busy} onClick={() => dialog.current?.close()}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save entry'}</button></div>
      </form>
    </dialog>
  </main>
}
