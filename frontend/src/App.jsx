import { Suspense, lazy, useEffect } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import Landing from './pages/Landing'
import AppShell from './components/app/AppShell'
import NewRehearsal from './pages/NewRehearsal'
import NotFound from './pages/NotFound'
import Login from './pages/Login'
import { RequireAuth } from './auth'

// The heavy pages (MediaPipe, recharts) load on demand so the landing page stays light.
const Rehearsal = lazy(() => import('./pages/Rehearsal'))
const Session = lazy(() => import('./pages/Session'))
const Report = lazy(() => import('./pages/Report'))

// "/" is the landing page (public). Everything under "/practice" is the app (sidebar + main column),
// which needs a session when auth is on; /login signs in and comes back.
export default function App() {
  const { pathname, hash } = useLocation()
  // New page starts at the top, unless we're jumping to a landing section.
  useEffect(() => { if (!hash) window.scrollTo(0, 0) }, [pathname, hash])

  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/practice" element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<NewRehearsal />} />
        <Route path="rehearsals/:id" element={<Lazy><Rehearsal /></Lazy>} />
        <Route path="takes/:id/session" element={<Lazy><Session /></Lazy>} />
        <Route path="takes/:id" element={<Lazy><Report /></Lazy>} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="*" element={<NotFound standalone />} />
    </Routes>
  )
}

function Lazy({ children }) {
  return <Suspense fallback={<div className="body"><p className="muted">Loading...</p></div>}>{children}</Suspense>
}
