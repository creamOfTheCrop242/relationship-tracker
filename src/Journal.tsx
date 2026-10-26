import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import Dashboard from './Dashboard'
import Needs from './Needs'

const categories = { intimacy: 'Intimacy', kindness: 'Kindness', conflict: 'Conflict', outing: 'Outing', alcohol: 'Alcohol', childcare: 'Childcare', custom: 'Custom' }
type Category = keyof typeof categories
type DetailValue = string | number | boolean
type Entry = { id: string; category: Category; description: string; occurred_at: string; person: string | null; mood: string | null; impact: string | null; notes: string | null; details: Record<string, DetailValue> }
type Relationship = { id: string; partner_name: string }
type Filters = { q: string; category: '' | Category; person: string; from: string; to: string }

const emptyFilters: Filters = { q: '', category: '', person: '', from: '', to: '' }

const titleCase = (value: DetailValue) => String(value).replaceAll('_', ' ').replace(/\b\w/g, letter => letter.toUpperCase())

function CategoryFields({ category, details, partnerName }: { category: Category; details: Record<string, DetailValue>; partnerName: string }) {
  const [intimacyType, setIntimacyType] = useState(String(details.type ?? ''))
  const rating = (name: string, label: string) => <label>{label} (optional)<select name={name} defaultValue={String(details[name.replace('detail_', '')] ?? '')}><option value="">Not specified</option>{[1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
  const people = <><option value="">Not specified</option><option value="me">Me</option><option value="partner">{partnerName}</option><option value="both">Both</option></>

  if (category === 'intimacy') return <div className="category-fields">
    <p className="eyebrow">INTIMACY DETAILS</p>
    <label>Type (optional)<select name="detail_type" value={intimacyType} onChange={event => setIntimacyType(event.target.value)}><option value="">Not specified</option><option value="sex">Sex</option><option value="kissing">Kissing</option><option value="cuddling">Cuddling</option><option value="affection">Affection</option><option value="emotional_closeness">Emotional closeness</option><option value="custom">Something else</option></select></label>
    {intimacyType === 'custom' && <label>Type description<input name="detail_custom_type" required maxLength={100} defaultValue={String(details.custom_type ?? '')} /></label>}
    {rating('detail_satisfaction', 'Satisfaction')}
  </div>
  if (category === 'kindness') return <div className="category-fields"><p className="eyebrow">KINDNESS DETAILS</p>
    <label>Who initiated it? (optional)<select name="detail_initiated_by" defaultValue={String(details.initiated_by ?? '')}>{people}</select></label>
    {rating('detail_appreciation', 'Appreciation')}
  </div>
  if (category === 'conflict') return <div className="category-fields"><p className="eyebrow">CONFLICT DETAILS</p>
    <label>Who was upset? (optional)<select name="detail_upset" defaultValue={String(details.upset ?? '')}>{people}</select></label>
    <label>Who initiated it? (optional)<select name="detail_initiated_by" defaultValue={String(details.initiated_by ?? '')}>{people}</select></label>
    <label>What caused it? (optional)<input name="detail_cause" maxLength={500} defaultValue={String(details.cause ?? '')} /></label>
    <label>Was it resolved? (optional)<select name="detail_resolved" defaultValue={details.resolved === true ? 'true' : details.resolved === false ? 'false' : ''}><option value="">Not specified</option><option value="true">Yes</option><option value="false">No</option></select></label>
    {rating('detail_intensity', 'Intensity')}
  </div>
  if (category === 'outing') return <div className="category-fields"><p className="eyebrow">OUTING DETAILS</p>
    <label>Activity (optional)<input name="detail_activity" maxLength={200} defaultValue={String(details.activity ?? '')} /></label>
    <label>Who attended? (optional)<select name="detail_attended_by" defaultValue={String(details.attended_by ?? '')}>{people}<option value="others">Others</option></select></label>
    {rating('detail_enjoyment', 'Enjoyment')}
  </div>
  if (category === 'alcohol') return <div className="category-fields"><p className="eyebrow">ALCOHOL DETAILS</p>
    <label>Who drank? (optional)<select name="detail_drank" defaultValue={String(details.drank ?? '')}>{people}</select></label>
    <label>Level (optional)<select name="detail_level" defaultValue={String(details.level ?? '')}><option value="">Not specified</option><option value="light">Light</option><option value="moderate">Moderate</option><option value="heavy">Heavy</option></select></label>
    <label>Context (optional)<input name="detail_context" maxLength={500} defaultValue={String(details.context ?? '')} /></label>
  </div>
  if (category === 'childcare') return <div className="category-fields"><p className="eyebrow">CHILDCARE DETAILS</p>
    <label>Who provided care? (optional)<select name="detail_provided_by" defaultValue={String(details.provided_by ?? '')}>{people}<option value="other">Someone else</option></select></label>
    <label>Approximate minutes (optional)<input name="detail_duration_minutes" type="number" min={1} max={1440} defaultValue={String(details.duration_minutes ?? '')} /></label>
    <label>Did it feel fair? (optional)<select name="detail_felt_fair" defaultValue={details.felt_fair === true ? 'true' : details.felt_fair === false ? 'false' : ''}><option value="">Not specified</option><option value="true">Yes</option><option value="false">No</option></select></label>
  </div>
  return <div className="category-fields"><p className="eyebrow">CUSTOM DETAILS</p>{rating('detail_rating', 'Rating')}</div>
}

function readDetails(category: Category, data: FormData): Record<string, DetailValue> {
  const fields: Record<Category, string[]> = {
    intimacy: ['type', 'custom_type', 'satisfaction'], kindness: ['initiated_by', 'appreciation'],
    conflict: ['upset', 'initiated_by', 'cause', 'resolved', 'intensity'],
    outing: ['activity', 'attended_by', 'enjoyment'], alcohol: ['drank', 'level', 'context'],
    childcare: ['provided_by', 'duration_minutes', 'felt_fair'], custom: ['rating'],
  }
  const numeric = new Set(['satisfaction', 'appreciation', 'intensity', 'enjoyment', 'duration_minutes', 'rating'])
  const boolean = new Set(['resolved', 'felt_fair'])
  return Object.fromEntries(fields[category].flatMap(key => {
    const value = String(data.get(`detail_${key}`) ?? '').trim()
    if (!value || (key === 'custom_type' && data.get('detail_type') !== 'custom')) return []
    return [[key, numeric.has(key) ? Number(value) : boolean.has(key) ? value === 'true' : value]]
  }))
}

function detailRows(entry: Entry, partnerName: string) {
  const labels: Record<string, string> = { type: 'Type', custom_type: 'Type', satisfaction: 'Satisfaction', initiated_by: 'Initiated by', appreciation: 'Appreciation', upset: 'Upset', cause: 'Cause', resolved: 'Resolved', intensity: 'Intensity', activity: 'Activity', attended_by: 'Attended by', enjoyment: 'Enjoyment', drank: 'Who drank', level: 'Level', context: 'Context', provided_by: 'Care provided by', duration_minutes: 'Duration', felt_fair: 'Felt fair', rating: 'Rating' }
  return Object.entries(entry.details ?? {}).filter(([key]) => !(key === 'custom_type' && entry.details.type === 'custom')).map(([key, value]) => {
    let display = value === true ? 'Yes' : value === false ? 'No' : titleCase(value)
    if (value === 'partner') display = partnerName
    if (['satisfaction', 'appreciation', 'intensity', 'enjoyment', 'rating'].includes(key)) display = `${value}/5`
    if (key === 'duration_minutes') display = `${value} minutes`
    if (key === 'type' && value === 'custom') display = String(entry.details.custom_type ?? 'Custom')
    return [labels[key] ?? titleCase(key), display]
  })
}

function localDate(value = new Date().toISOString()) {
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function eventPath(filters: Filters, offset = 0) {
  const params = new URLSearchParams({ limit: '50' })
  if (offset) params.set('offset', String(offset))
  if (filters.q.trim()) params.set('q', filters.q.trim())
  if (filters.category) params.set('category', filters.category)
  if (filters.person) params.set('person', filters.person)
  if (filters.from) params.set('occurred_from', new Date(`${filters.from}T00:00:00`).toISOString())
  if (filters.to) {
    const nextDay = new Date(`${filters.to}T00:00:00`)
    nextDay.setDate(nextDay.getDate() + 1)
    params.set('occurred_before', nextDay.toISOString())
  }
  return `/events?${params}`
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
  const [filterDraft, setFilterDraft] = useState<Filters>(emptyFilters)
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters)
  const [dashboardVersion, setDashboardVersion] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)

  async function replaceEntries(filters: Filters) {
    const rows = await api<Entry[]>(eventPath(filters))
    setEntries(rows)
    setHasMore(rows.length === 50)
  }

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [rel, rows] = await Promise.all([api<Relationship | null>('/relationship'), api<Entry[]>(eventPath(appliedFilters))])
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
      const body = { category, description: String(data.get('description')).trim(), occurred_at: new Date(String(data.get('occurred_at'))).toISOString(), person: optional('person'), mood: optional('mood'), impact: optional('impact'), notes: optional('notes'), details: readDetails(category, data) }
      await api(editing ? `/events/${editing.id}` : '/events', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) })
      dialog.current?.close()
      setNotice(editing ? 'Entry updated.' : 'Entry saved.')
      await replaceEntries(appliedFilters)
      setDashboardVersion(value => value + 1)
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
      await replaceEntries(appliedFilters)
      setDashboardVersion(value => value + 1)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function loadMore() {
    setBusy(true)
    setError('')
    try {
      const rows = await api<Entry[]>(eventPath(appliedFilters, entries.length))
      setEntries(previous => [...previous, ...rows.filter(row => !previous.some(item => item.id === row.id))])
      setHasMore(rows.length === 50)
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    if (filterDraft.from && filterDraft.to && filterDraft.from > filterDraft.to) {
      setError('The start date must be on or before the end date.')
      return
    }
    setLoading(true)
    try {
      const next = { ...filterDraft }
      await replaceEntries(next)
      setAppliedFilters(next)
    } catch (err) { setError((err as Error).message) }
    finally { setLoading(false) }
  }

  async function clearFilters() {
    setError('')
    setLoading(true)
    try {
      await replaceEntries(emptyFilters)
      setFilterDraft(emptyFilters)
      setAppliedFilters(emptyFilters)
    } catch (err) { setError((err as Error).message) }
    finally { setLoading(false) }
  }

  const filtersActive = Object.values(appliedFilters).some(Boolean)

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
    <Dashboard partnerName={relationship?.partner_name ?? 'Partner'} refreshKey={dashboardVersion} onLog={() => openForm('kindness')} />
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
      <form className="timeline-filters" onSubmit={applyFilters}>
        <label className="filter-search">Search<input type="search" maxLength={200} value={filterDraft.q} onChange={event => setFilterDraft(current => ({ ...current, q: event.target.value }))} placeholder="Words in an entry" disabled={loading || busy} /></label>
        <label>Category<select value={filterDraft.category} onChange={event => setFilterDraft(current => ({ ...current, category: event.target.value as Filters['category'] }))} disabled={loading || busy}><option value="">All categories</option>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        <label>Person<select value={filterDraft.person} onChange={event => setFilterDraft(current => ({ ...current, person: event.target.value }))} disabled={loading || busy}><option value="">Anyone</option><option value="me">Me</option><option value="partner">{relationship?.partner_name ?? 'Partner'}</option><option value="both">Both</option><option value="neither">Neither</option></select></label>
        <label>From<input type="date" value={filterDraft.from} onChange={event => setFilterDraft(current => ({ ...current, from: event.target.value }))} disabled={loading || busy} /></label>
        <label>To<input type="date" value={filterDraft.to} onChange={event => setFilterDraft(current => ({ ...current, to: event.target.value }))} disabled={loading || busy} /></label>
        <div className="filter-actions"><button className="primary-button" disabled={loading || busy}>{loading ? 'Filtering…' : 'Apply'}</button><button type="button" className="text-button" onClick={() => void clearFilters()} disabled={loading || busy || (!filtersActive && !Object.values(filterDraft).some(Boolean))}>Clear</button></div>
      </form>
      {loading ? <p role="status">Loading your entries…</p> : !entries.length && !error ? <div className="empty-state"><span className="empty-icon">✦</span><p>{filtersActive ? 'No entries match these filters.' : 'Your first entry will start your timeline.'}</p></div> : <div className="timeline">{entries.map(entry => <article className="entry-card" key={entry.id}>
        <div className="entry-meta"><span className="status-pill">{categories[entry.category]}</span><time dateTime={entry.occurred_at}>{new Date(entry.occurred_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time></div>
        <h3>{entry.description}</h3>
        {entry.person && <p className="muted">Involved: {entry.person === 'partner' ? relationship?.partner_name ?? 'Partner' : entry.person}</p>}
        {entry.mood && <p>Mood: {entry.mood}</p>}{entry.impact && <p>Impact: {entry.impact}</p>}
        {!!detailRows(entry, relationship?.partner_name ?? 'Partner').length && <dl className="entry-details">{detailRows(entry, relationship?.partner_name ?? 'Partner').map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
        {entry.notes && <p className="entry-notes">{entry.notes}</p>}
        <div className="entry-actions"><button className="text-button" disabled={busy} onClick={() => openForm(entry.category, entry)}>Edit<span className="sr-only"> {entry.description}</span></button><button className="text-button danger" disabled={busy} onClick={() => void remove(entry)}>Delete<span className="sr-only"> {entry.description}</span></button></div>
      </article>)}</div>}
      {hasMore && !loading && <button className="primary-button load-more" disabled={busy} onClick={() => void loadMore()}>{busy ? 'Loading…' : 'Load older entries'}</button>}
    </section>
    <Needs partnerName={relationship?.partner_name ?? 'Partner'} onChanged={() => setDashboardVersion(value => value + 1)} />
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
          <CategoryFields key={category} category={category} details={editing?.category === category ? editing.details ?? {} : {}} partnerName={relationship?.partner_name ?? 'Partner'} />
          <label>Mood (optional)<input name="mood" maxLength={100} defaultValue={editing?.mood ?? ''} /></label>
          <label>Impact (optional)<input name="impact" maxLength={200} defaultValue={editing?.impact ?? ''} /></label>
          <label>Notes (optional)<textarea name="notes" rows={4} maxLength={10000} defaultValue={editing?.notes ?? ''} /></label>
        </fieldset>
        <div className="form-actions"><button type="button" className="text-button" disabled={busy} onClick={() => dialog.current?.close()}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save entry'}</button></div>
      </form>
    </dialog>
  </main>
}
