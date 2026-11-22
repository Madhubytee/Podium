import { createContext, useContext, useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { authEnabled, supabase } from './lib/supabase'

// Supabase session for the app. With auth off (no VITE_SUPABASE_URL), there is no session and
// nothing is gated: everything works as local dev always has.
const AuthContext = createContext({ enabled: false, ready: true, session: null, user: null, signOut: async () => {} })

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [ready, setReady] = useState(!authEnabled)

  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true) })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => { setSession(s); setReady(true) })
    return () => data.subscription.unsubscribe()
  }, [])

  const value = {
    enabled: authEnabled,
    ready,
    session,
    user: session?.user ?? null,
    signOut: async () => { await supabase?.auth.signOut() },
  }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)

// Wraps /practice: no session means /login, then back here after signing in.
export function RequireAuth({ children }) {
  const { enabled, ready, session } = useAuth()
  const { pathname, search } = useLocation()
  if (!enabled) return children
  if (!ready) return null
  if (!session) return <Navigate to={`/login?next=${encodeURIComponent(pathname + search)}`} replace />
  return children
}
