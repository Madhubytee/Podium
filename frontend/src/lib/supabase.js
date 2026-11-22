// Supabase Auth client, or null when VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY aren't set.
// With no client, auth is off: no login, and the backend runs without auth too (local dev).
import { createClient } from '@supabase/supabase-js'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_ANON_KEY

export const supabase = url && key ? createClient(url, key) : null
export const authEnabled = Boolean(supabase)

// The current access token, kept in sync so plain URLs (video, clips, the live socket) can carry it.
let token = null
if (supabase) {
  supabase.auth.getSession().then(({ data }) => { token = data.session?.access_token ?? null })
  supabase.auth.onAuthStateChange((_event, session) => { token = session?.access_token ?? null })
}
export const currentToken = () => token

// For fetch: asks Supabase, which refreshes an expired token first.
export async function freshToken() {
  if (!supabase) return null
  const { data } = await supabase.auth.getSession()
  token = data.session?.access_token ?? null
  return token
}
