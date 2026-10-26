import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'

type NeedUpdate = { id: string; occurred_on: string; status: 'met' | 'partly_met' | 'not_met'; what_happened: string; satisfaction: number; notes: string | null }
type Need = {
  id: string; person: 'me' | 'partner'; name: string; description: string | null; why_matters: string | null;
  importance: 'low' | 'medium' | 'high'; desired_amount: number | null;
  desired_period: 'per_day' | 'per_week' | 'per_month' | 'custom' | 'as_needed' | 'no_target';
  custom_period_days: number | null; confirmed_by_partner: 'yes' | 'no' | 'unknown'; active: boolean; updates: NeedUpdate[]
}

const targetedPeriods = new Set(['per_day', 'per_week', 'per_month', 'custom'])
const today = () => {
  const now = new Date()
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
const labels = { met: 'Met', partly_met: 'Partly met', not_met: 'Not met' }

function cadence(need: Need) {
  if (need.desired_period === 'as_needed') return 'As needed'
  if (need.desired_period === 'no_target') return 'No cadence target'
  const period = need.desired_period === 'custom' ? `every ${need.custom_period_days} days` : need.desired_period.replace('per_', 'per ')
  return `${need.desired_amount} ${need.desired_amount === 1 ? 'time' : 'times'} ${period}`
}

export default function Needs({ partnerName, onChanged }: { partnerName: string; onChanged: () => void }) {
  const [needs, setNeeds] = useState<Need[]>([])
  const [showArchived, setShowArchived] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState<Need | null>(null)
  const [selectedNeed, setSelectedNeed] = useState<Need | null>(null)
  const [editingUpdate, setEditingUpdate] = useState<NeedUpdate | null>(null)
  const [person, setPerson] = useState<'me' | 'partner'>('me')
  const [period, setPeriod] = useState<Need['desired_period']>('no_target')
  const [formVersion, setFormVersion] = useState(0)
  const [updateVersion, setUpdateVersion] = useState(0)
  const needDialog = useRef<HTMLDialogElement>(null)
  const updateDialog = useRef<HTMLDialogElement>(null)

  async function load(archived = showArchived) {
    setLoading(true)
    setError('')
    try { setNeeds(await api<Need[]>(`/needs${archived ? '?include_archived=true' : ''}`)) }
    catch (err) { setError((err as Error).message) }
    finally { setLoading(false) }
  }
  useEffect(() => { void load(showArchived) }, [showArchived])

  function openNeed(need: Need | null = null) {
    setEditing(need)
    setPerson(need?.person ?? 'me')
    setPeriod(need?.desired_period ?? 'no_target')
    setFormVersion(value => value + 1)
    setError('')
    needDialog.current?.showModal()
  }

  async function saveNeed(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const optional = (key: string) => String(data.get(key) ?? '').trim() || null
    const targeted = targetedPeriods.has(period)
    const body = {
      person, name: String(data.get('name')).trim(), description: optional('description'), why_matters: optional('why_matters'),
      importance: String(data.get('importance')), desired_amount: targeted ? Number(data.get('desired_amount')) : null,
      desired_period: period, custom_period_days: period === 'custom' ? Number(data.get('custom_period_days')) : null,
      confirmed_by_partner: person === 'partner' ? String(data.get('confirmed_by_partner')) : 'unknown', active: editing?.active ?? true,
    }
    setBusy(true)
    setError('')
    try {
      await api(editing ? `/needs/${editing.id}` : '/needs', { method: editing ? 'PUT' : 'POST', body: JSON.stringify(body) })
      needDialog.current?.close()
      setNotice(editing ? 'Need updated.' : 'Need added.')
      await load()
      onChanged()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function toggleArchive(need: Need) {
    setBusy(true)
    setError('')
    try {
      await api(`/needs/${need.id}/archive`, { method: 'PATCH', body: JSON.stringify({ active: !need.active }) })
      setNotice(need.active ? 'Need archived.' : 'Need restored.')
      await load()
      onChanged()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  function openUpdate(need: Need, update: NeedUpdate | null = null) {
    setSelectedNeed(need)
    setEditingUpdate(update)
    setUpdateVersion(value => value + 1)
    setError('')
    updateDialog.current?.showModal()
  }

  async function saveUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedNeed) return
    const data = new FormData(event.currentTarget)
    const notes = String(data.get('notes') ?? '').trim() || null
    const body = { occurred_on: String(data.get('occurred_on')), status: String(data.get('status')), what_happened: String(data.get('what_happened')).trim(), satisfaction: Number(data.get('satisfaction')), notes }
    setBusy(true)
    setError('')
    try {
      const path = `/needs/${selectedNeed.id}/updates${editingUpdate ? `/${editingUpdate.id}` : ''}`
      await api(path, { method: editingUpdate ? 'PUT' : 'POST', body: JSON.stringify(body) })
      updateDialog.current?.close()
      setNotice(editingUpdate ? 'Need update edited.' : 'Need update saved.')
      await load()
      onChanged()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  async function removeUpdate(need: Need, update: NeedUpdate) {
    if (!window.confirm('Delete this need update? This cannot be undone.')) return
    setBusy(true)
    setError('')
    try {
      await api(`/needs/${need.id}/updates/${update.id}`, { method: 'DELETE' })
      setNotice('Need update deleted.')
      await load()
      onChanged()
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }

  return <section className="section-block needs-section">
    <div className="section-heading"><div><p className="eyebrow">WHAT MATTERS</p><h2>Relationship needs</h2></div><button className="primary-button" disabled={loading || busy} onClick={() => openNeed()}>＋ Add need</button></div>
    <p className="muted needs-intro">Cadence describes what you want, not an obligation or quota.</p>
    <label className="archive-toggle"><input type="checkbox" checked={showArchived} onChange={event => setShowArchived(event.target.checked)} disabled={loading || busy} /> Show archived needs</label>
    {error && <p className="auth-warning" role="alert">{error}</p>}
    <p className="save-notice" role="status">{notice}</p>
    {loading ? <p role="status">Loading relationship needs…</p> : !needs.length ? <div className="empty-state"><span className="empty-icon">✦</span><p>{showArchived ? 'No needs have been added yet.' : 'Add what matters to you or what you believe matters to your partner.'}</p></div> : <div className="needs-list">{needs.map(need => <article className={`need-card${need.active ? '' : ' archived'}`} key={need.id}>
      <div className="need-header"><div><p className="eyebrow">{need.person === 'me' ? 'FOR ME' : `FOR ${partnerName.toUpperCase()}`}</p><h3>{need.name}</h3></div><span className={`importance-pill ${need.importance}`}>{need.importance}</span></div>
      {need.description && <p>{need.description}</p>}
      {need.why_matters && <p className="muted"><strong>Why it matters:</strong> {need.why_matters}</p>}
      <p className="need-cadence">{cadence(need)}</p>
      {need.person === 'partner' && <p className="confirmation-note">{need.confirmed_by_partner === 'yes' ? `Confirmed by ${partnerName}` : need.confirmed_by_partner === 'no' ? `Not confirmed by ${partnerName}` : `Your understanding — not confirmed by ${partnerName}`}</p>}
      <div className="need-actions"><button className="text-button" disabled={busy} onClick={() => openUpdate(need)}>Add update</button><button className="text-button" disabled={busy} onClick={() => openNeed(need)}>Edit</button><button className="text-button" disabled={busy} onClick={() => void toggleArchive(need)}>{need.active ? 'Archive' : 'Restore'}</button></div>
      <div className="need-history"><h4>History</h4>{!need.updates.length ? <p className="muted">No updates recorded.</p> : need.updates.map(update => <div className="need-update" key={update.id}>
        <div><span className={`status-pill need-status ${update.status}`}>{labels[update.status]}</span><time dateTime={update.occurred_on}>{new Date(`${update.occurred_on}T00:00:00`).toLocaleDateString(undefined, { dateStyle: 'medium' })}</time></div>
        <p>{update.what_happened}</p><p className="muted">Satisfaction: {update.satisfaction}/5{update.notes ? ` · ${update.notes}` : ''}</p>
        <div className="need-update-actions"><button className="text-button" disabled={busy} onClick={() => openUpdate(need, update)}>Edit</button><button className="text-button danger" disabled={busy} onClick={() => void removeUpdate(need, update)}>Delete</button></div>
      </div>)}</div>
    </article>)}</div>}

    <dialog ref={needDialog} className="entry-dialog" aria-labelledby="need-title" onCancel={event => { if (busy) event.preventDefault() }}>
      <form key={formVersion} onSubmit={saveNeed}><h2 id="need-title">{editing ? 'Edit need' : 'Add a relationship need'}</h2><p className="muted">Describe what matters without turning it into a scorecard.</p>{error && <p className="auth-warning" role="alert">{error}</p>}<fieldset disabled={busy}>
        <label>Whose need?<select value={person} onChange={event => setPerson(event.target.value as 'me' | 'partner')}><option value="me">Mine</option><option value="partner">{partnerName}'s</option></select></label>
        <label>Need name<input name="name" required maxLength={200} defaultValue={editing?.name ?? ''} placeholder="Quality time" /></label>
        <label>Description (optional)<textarea name="description" rows={3} maxLength={2000} defaultValue={editing?.description ?? ''} /></label>
        <label>Why it matters (optional)<textarea name="why_matters" rows={3} maxLength={2000} defaultValue={editing?.why_matters ?? ''} /></label>
        <label>Importance<select name="importance" defaultValue={editing?.importance ?? 'medium'}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></label>
        <label>Desired period<select value={period} onChange={event => setPeriod(event.target.value as Need['desired_period'])}><option value="no_target">No target</option><option value="as_needed">As needed</option><option value="per_day">Per day</option><option value="per_week">Per week</option><option value="per_month">Per month</option><option value="custom">Custom period</option></select></label>
        {targetedPeriods.has(period) && <label>Desired amount<input name="desired_amount" type="number" min={1} max={1000} required defaultValue={editing?.desired_amount ?? 1} /></label>}
        {period === 'custom' && <label>Number of days in custom period<input name="custom_period_days" type="number" min={1} max={3650} required defaultValue={editing?.custom_period_days ?? 7} /></label>}
        {person === 'partner' && <label>Has {partnerName} confirmed this?<select name="confirmed_by_partner" defaultValue={editing?.confirmed_by_partner ?? 'unknown'}><option value="unknown">Unknown / not discussed</option><option value="yes">Yes</option><option value="no">No</option></select></label>}
      </fieldset><div className="form-actions"><button type="button" className="text-button" disabled={busy} onClick={() => needDialog.current?.close()}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save need'}</button></div></form>
    </dialog>

    <dialog ref={updateDialog} className="entry-dialog" aria-labelledby="update-title" onCancel={event => { if (busy) event.preventDefault() }}>
      <form key={updateVersion} onSubmit={saveUpdate}><h2 id="update-title">{editingUpdate ? 'Edit update' : `Update ${selectedNeed?.name ?? 'need'}`}</h2><p className="muted">Record what happened. Missing entries remain unknown.</p>{error && <p className="auth-warning" role="alert">{error}</p>}<fieldset disabled={busy}>
        <label>Date<input name="occurred_on" type="date" required defaultValue={editingUpdate?.occurred_on ?? today()} /></label>
        <label>Status<select name="status" defaultValue={editingUpdate?.status ?? 'met'}><option value="met">Met</option><option value="partly_met">Partly met</option><option value="not_met">Not met</option></select></label>
        <label>What happened?<textarea name="what_happened" rows={3} required maxLength={1000} defaultValue={editingUpdate?.what_happened ?? ''} /></label>
        <label>Satisfaction<select name="satisfaction" defaultValue={editingUpdate?.satisfaction ?? 3}>{[1, 2, 3, 4, 5].map(value => <option key={value} value={value}>{value}/5</option>)}</select></label>
        <label>Notes (optional)<textarea name="notes" rows={3} maxLength={10000} defaultValue={editingUpdate?.notes ?? ''} /></label>
      </fieldset><div className="form-actions"><button type="button" className="text-button" disabled={busy} onClick={() => updateDialog.current?.close()}>Cancel</button><button className="primary-button" disabled={busy}>{busy ? 'Saving…' : 'Save update'}</button></div></form>
    </dialog>
  </section>
}
