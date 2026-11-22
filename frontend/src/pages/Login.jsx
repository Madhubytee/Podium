import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth'
import Wordmark from '../components/Wordmark'
import { supabase } from '../lib/supabase'

// Only same-site paths, so ?next= can't send anyone off to another site.
const safeNext = (next) => (next && next.startsWith('/') && !next.startsWith('//') ? next : '/practice')

const MODES = [
  { id: 'in', name: 'Sign in' },
  { id: 'up', name: 'Create an account' },
]

// /login: email and password, or a magic link. Plain paper, one Oli, rules instead of boxes.
export default function Login() {
  const { enabled, ready, session } = useAuth()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const [mode, setMode] = useState('in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(null)

  if (!enabled) return <Navigate to={next} replace />
  if (ready && session) return <Navigate to={next} replace />

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    setSent(null)
    try { await fn() } catch (e) { setError(e.message || 'Something went wrong. Try again.') }
    setBusy(false)
  }

  const submit = (e) => {
    e.preventDefault()
    if (!email.trim() || !password) { setError('Add your email and a password.'); return }
    run(async () => {
      if (mode === 'in') {
        const { error: err } = await supabase.auth.signInWithPassword({ email: email.trim(), password })
        if (err) throw err
      } else {
        const { data, error: err } = await supabase.auth.signUp({
          email: email.trim(), password,
          options: { emailRedirectTo: `${location.origin}/login?next=${encodeURIComponent(next)}` },
        })
        if (err) throw err
        if (!data.session) setSent(`Almost there. Check ${email.trim()} for a link to confirm your account.`)
      }
    })
  }

  const magic = () => {
    if (!email.trim()) { setError('Add your email first and Oli will send the link there.'); return }
    run(async () => {
      const { error: err } = await supabase.auth.signInWithOtp({
        email: email.trim(),
        options: { emailRedirectTo: `${location.origin}/login?next=${encodeURIComponent(next)}` },
      })
      if (err) throw err
      setSent(`Sent. Open the link in ${email.trim()} on this device to sign in.`)
    })
  }

  return (
    <div className="login-page">
      <header className="topnav">
        <div className="wrap"><Wordmark to="/" /></div>
      </header>
      <div className="body">
        <form className="setup login" noValidate onSubmit={submit}>
          <div className="ask">
            <img src="/oli-presentation.webp" alt="Oli" width="104" height="104" />
            <div>
              <h1>{mode === 'in' ? 'Welcome back.' : "Let's get you set up."}</h1>
              <p>{mode === 'in' ? 'Sign in and Oli will pick up where you left off.' : 'Your rehearsals and takes stay in your account.'}</p>
            </div>
          </div>

          <div className="tabs" role="tablist" aria-label="Sign in or create an account">
            {MODES.map((m) => (
              <button key={m.id} type="button" role="tab" className="occ" aria-selected={mode === m.id}
                      onClick={() => { setMode(m.id); setError(null); setSent(null) }}>
                {m.name}
              </button>
            ))}
          </div>

          <div className="fields">
            <label className="field">
              <span className="label">Email</span>
              <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@school.edu" />
            </label>
            <label className="field">
              <span className="label">Password {mode === 'up' && <small>at least 6 characters</small>}</span>
              <input type="password" autoComplete={mode === 'in' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
          </div>

          {error && <p className="err" role="alert">{error}</p>}
          {sent && <p className="sent" role="status">{sent}</p>}

          <div className="start-row">
            <button className="btn primary" type="submit" disabled={busy}>{busy ? 'One moment...' : mode === 'in' ? 'Sign in' : 'Create account'}</button>
            <span>or</span>
            <button className="text-btn" type="button" disabled={busy} onClick={magic}>Email me a magic link</button>
          </div>
        </form>
      </div>
    </div>
  )
}
