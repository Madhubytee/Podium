import { useCallback, useEffect, useState } from 'react'
import { Outlet, useLocation, useOutletContext } from 'react-router-dom'
import { api } from '../../api'
import Sidebar from './Sidebar'

// The app frame: rehearsal sidebar (a drawer with a backdrop at phone width), the top bar with
// the crumb, and the routed page. Pages talk to the frame through useShell().
export default function AppShell() {
  const [rehearsals, setRehearsals] = useState(null) // null while loading
  const [listError, setListError] = useState(null)
  const [open, setOpen] = useState(false)
  const [crumb, setCrumb] = useState({ title: 'New rehearsal' })
  const { pathname } = useLocation()

  const refresh = useCallback(() => api.listRehearsals()
    .then((list) => { setRehearsals(list); setListError(null) })
    .catch((e) => setListError(e.status === 429 ? e.message : "Couldn't reach Podium's server.")), [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => { setOpen(false) }, [pathname])
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="app">
      <Sidebar
        rehearsals={rehearsals}
        error={listError}
        open={open}
        activeId={crumb.rehearsalId}
        onClose={() => setOpen(false)}
      />
      {open && <div className="scrim" onClick={() => setOpen(false)} />}

      <main className="main">
        <div className="main-top">
          <button className="icon-btn menu" type="button" aria-label="Open rehearsals" aria-controls="side"
                  aria-expanded={open} onClick={() => setOpen(true)}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h10" /></svg>
          </button>
          <span className="crumb">
            {crumb.title}{crumb.sub && <span> · {crumb.sub}</span>}
          </span>
        </div>
        <Outlet context={{ refresh, setCrumb }} />
      </main>
    </div>
  )
}

// { refresh(): reload the sidebar, setCrumb({ title, sub?, rehearsalId? }) }
export const useShell = () => useOutletContext()
