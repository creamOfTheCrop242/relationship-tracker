import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from './api'
import PwaControls from './PwaControls'

const loveLanguages = {
  words_of_affirmation: 'Words of affirmation', quality_time: 'Quality time', physical_touch: 'Physical touch',
  acts_of_service: 'Acts of service', receiving_gifts: 'Receiving gifts',
} as const
type LoveLanguage = keyof typeof loveLanguages
type Profile = { id: string; person: 'me' | 'partner'; display_name: string; love_languages: LoveLanguage[]; hobbies: string[]; interests: string[]; goals: string[]; notes: string | null }
type NeedRequest = { id: string; title: string; active: boolean; desired_amount: number | null; desired_period: string }
type Need = { id: string; person: 'me' | 'partner'; name: string; description: string | null; importance: 'low' | 'medium' | 'high'; desired_amount: number | null; desired_period: string; requests: NeedRequest[] }

const lines = (value: FormDataEntryValue | null) => String(value ?? '').split('\n').map(item => item.trim()).filter(Boolean)
const cadence = (item: Need | NeedRequest) => item.desired_amount ? `${item.desired_amount} ${item.desired_amount === 1 ? 'time' : 'times'} ${item.desired_period.replace('per_', 'per ')}` : item.desired_period.replaceAll('_', ' ')

function ProfileCard({ profile, needs, onSaved }: { profile: Profile; needs: Need[]; onSaved: (profile: Profile) => void }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    setBusy(true); setError(''); setNotice('')
    try {
      const updated = await api<Profile>(`/profiles/${profile.person}`, { method: 'PUT', body: JSON.stringify({
        love_languages: data.getAll('love_languages'), hobbies: lines(data.get('hobbies')),
        interests: lines(data.get('interests')), goals: lines(data.get('goals')),
        notes: String(data.get('notes') ?? '').trim() || null,
      }) })
      onSaved(updated)
      setNotice('Profile saved.')
    } catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  return <article className="profile-card">
    <div className="profile-heading"><div className="profile-avatar" aria-hidden="true">{profile.display_name.slice(0, 1).toUpperCase()}</div><div><p className="eyebrow">{profile.person === 'me' ? 'MY PROFILE' : 'PARTNER PROFILE'}</p><h2>{profile.display_name}</h2></div></div>
    {profile.person === 'partner' && <p className="confirmation-note">This is your private understanding of your partner. It does not indicate that they confirmed these details.</p>}
    <form onSubmit={save}>
      {error && <p className="auth-warning" role="alert">{error}</p>}<p className="save-notice" role="status">{notice}</p>
      <fieldset disabled={busy}><legend>Love languages</legend><div className="love-language-grid">{Object.entries(loveLanguages).map(([value, label]) => <label key={value} className="profile-check"><input type="checkbox" name="love_languages" value={value} defaultChecked={profile.love_languages.includes(value as LoveLanguage)} /> {label}</label>)}</div></fieldset>
      <div className="profile-fields">
        <label>Hobbies <span className="muted">One per line</span><textarea name="hobbies" rows={4} maxLength={5000} defaultValue={profile.hobbies.join('\n')} placeholder="Hiking&#10;Cooking" /></label>
        <label>Interests <span className="muted">One per line</span><textarea name="interests" rows={4} maxLength={5000} defaultValue={profile.interests.join('\n')} placeholder="Live music&#10;Travel" /></label>
        <label>Goals <span className="muted">One per line</span><textarea name="goals" rows={4} maxLength={5000} defaultValue={profile.goals.join('\n')} placeholder="Run a 5K&#10;Plan a vacation" /></label>
        <label>Anything else<textarea name="notes" rows={4} maxLength={5000} defaultValue={profile.notes ?? ''} placeholder="Preferences, important dates, or things to remember…" /></label>
      </div>
      <button className="primary-button" disabled={busy}>{busy ? 'Saving…' : `Save ${profile.person === 'me' ? 'my' : 'partner'} profile`}</button>
    </form>
    <section className="profile-needs"><h3>Needs and requests</h3>{!needs.length ? <p className="muted">No active needs recorded for this person.</p> : <div>{needs.map(need => <article key={need.id}><div><strong>{need.name}</strong><span className={`importance-pill ${need.importance}`}>{need.importance}</span></div>{need.description && <p>{need.description}</p>}<small>Broad need: {cadence(need)}</small>{need.requests.some(request => request.active) && <ul>{need.requests.filter(request => request.active).map(request => <li key={request.id}><span>{request.title}</span><small>{cadence(request)}</small></li>)}</ul>}</article>)}</div>}</section>
  </article>
}

export default function Profiles({ onBack, signOut }: { onBack: () => void; signOut: () => void }) {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [needs, setNeeds] = useState<Need[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    Promise.all([api<Profile[]>('/profiles'), api<Need[]>('/needs')]).then(([profileRows, needRows]) => { setProfiles(profileRows); setNeeds(needRows) }).catch(err => setError(err.message)).finally(() => setLoading(false))
  }, [])
  return <><PwaControls /><main className="app-shell profiles-page"><header className="topbar"><button className="text-button" onClick={onBack}>← Journal</button><div><p className="eyebrow">PRIVATE PROFILES</p><h1>You and your partner</h1></div><button className="text-button" onClick={signOut}>Sign out</button></header>
    <div className="profiles-intro"><h2>Remember the whole person</h2><p className="muted">Keep useful context close to the needs and moments you already track.</p></div>
    {error && <p className="auth-warning" role="alert">{error}</p>}
    {loading ? <p role="status">Loading profiles…</p> : <div className="profiles-grid">{profiles.map(profile => <ProfileCard key={profile.id} profile={profile} needs={needs.filter(need => need.person === profile.person)} onSaved={updated => setProfiles(rows => rows.map(row => row.id === updated.id ? updated : row))} />)}</div>}
  </main></>
}
