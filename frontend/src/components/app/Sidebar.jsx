import { NavLink } from 'react-router-dom'
import { useAuth } from '../../auth'
import Wordmark from '../Wordmark'

const DAY = 86400

// Today, Previous 7 days, then one group per month ("October", or "October 2025" for older years).
function groupOf(seconds) {
  const d = new Date(seconds * 1000)
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
  if (seconds >= startOfToday) return 'Today'
  if (seconds >= startOfToday - 7 * DAY) return 'Previous 7 days'
  const month = d.toLocaleDateString(undefined, { month: 'long' })
  return d.getFullYear() === now.getFullYear() ? month : `${month} ${d.getFullYear()}`
}

function groupRehearsals(list) {
  const groups = []
  for (const r of [...list].sort((a, b) => b.created_at - a.created_at)) {
    const name = groupOf(r.created_at)
    let g = groups.find((x) => x.name === name)
    if (!g) groups.push(g = { name, items: [] })
    g.items.push(r)
  }
  return groups
}

export default function Sidebar({ rehearsals, error, open, activeId, onClose }) {
  const { enabled, user, signOut } = useAuth()
  return (
    <aside className={`side${open ? ' open' : ''}`} id="side" aria-label="Rehearsals">
      <div className="side-head">
        <Wordmark to="/" />
        <button className="icon-btn" type="button" aria-label="Close rehearsals" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
      </div>

      <NavLink end to="/practice" className={({ isActive }) => `new-btn${isActive ? ' on' : ''}`}>
        <span className="plus"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg></span>
        New rehearsal
      </NavLink>

      {error && <p className="side-note">{error}</p>}
      {!error && rehearsals?.length === 0 && <p className="side-note">Your rehearsals will show up here.</p>}

      {rehearsals && groupRehearsals(rehearsals).map((g) => (
        <div className="group" key={g.name}>
          <h3>{g.name}</h3>
          {g.items.map((r) => (
            <NavLink
              key={r.id}
              to={`/practice/rehearsals/${r.id}`}
              className={({ isActive }) => `thread${isActive || r.id === activeId ? ' active' : ''}`}
              title={r.title}
            >
              <span className="tn">{r.title}</span>
              <span className="tk">{r.take_count ? `Take ${r.take_count}` : 'No takes'}</span>
            </NavLink>
          ))}
        </div>
      ))}

      <div className="side-foot">
        <span className="avatar" aria-hidden="true">{user?.email ? user.email.slice(0, 2).toUpperCase() : 'YOU'}</span>
        <span className="who">
          <span className="email" title={user?.email}>{enabled ? user?.email : 'Your account'}</span>
          {enabled && <button type="button" className="text-btn mute small" onClick={signOut}>Sign out</button>}
        </span>
      </div>
    </aside>
  )
}
