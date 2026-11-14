// Thin wrapper around the Podium API. Every call throws an Error with the server's message
// (for a 429 that's the "try again in N seconds" line, shown as is).
// With auth on, every request carries the Supabase access token; a 401 signs out and goes to /login.

import { currentToken, freshToken, supabase } from './lib/supabase'

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function signedOut() {
  await supabase?.auth.signOut({ scope: 'local' }).catch(() => {})
  const next = location.pathname + location.search
  if (!location.pathname.startsWith('/login')) location.assign(`/login?next=${encodeURIComponent(next)}`)
}

async function request(path, options = {}) {
  const token = await freshToken()
  const headers = { ...(options.headers ?? {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(`/api${path}`, { ...options, headers })
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
    } catch { /* not JSON */ }
    if (res.status === 401 && supabase) {
      signedOut()
      message = 'Your session ended. Sign in again to keep going.'
    }
    throw new ApiError(message, res.status)
  }
  return res.json()
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body ?? {}),
})

// URLs the browser opens itself (video tags, the WebSocket) can't send headers, so the token rides along.
function withToken(url) {
  const token = currentToken()
  return token ? `${url}${url.includes('?') ? '&' : '?'}access_token=${encodeURIComponent(token)}` : url
}

export const api = {
  health: () => request('/health'),
  me: () => request('/me'),
  listRehearsals: () => request('/rehearsals'),
  getRehearsal: (id) => request(`/rehearsals/${id}`),
  createRehearsal: (body) => request('/rehearsals', json('POST', body)),
  deleteRehearsal: (id) => request(`/rehearsals/${id}`, { method: 'DELETE' }),
  uploadFiles: (id, files) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f))
    return request(`/rehearsals/${id}/files`, { method: 'POST', body: form })
  },
  progress: (id) => request(`/rehearsals/${id}/progress`),
  createTake: (rehearsalId, mode) => request(`/rehearsals/${rehearsalId}/takes`, json('POST', { mode })),
  getTake: (id) => request(`/takes/${id}`),
  facts: (takeId, ids) => request(`/takes/${takeId}/facts?ids=${ids.join(',')}`),
  uploadTake: (id, blob, filename) => {
    const form = new FormData()
    form.append('file', blob, filename)
    return request(`/takes/${id}/upload`, { method: 'POST', body: form })
  },
  clipUrl: (takeId, start, end) => withToken(`/api/takes/${takeId}/clip?start=${start}&end=${end}`),
  videoUrl: (takeId) => withToken(`/api/takes/${takeId}/video`),
  liveSocket: async (takeId) => {
    await freshToken()
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    return new WebSocket(withToken(`${proto}://${location.host}/api/takes/${takeId}/live`))
  },
}

// Occasion data (names, Oli's lines, options) lives in config/occasions.js.
