// 75 -> "1:15"
export function clock(sec) {
  const s = Math.max(0, Math.floor(sec ?? 0))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

export const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`

export function shortDate(seconds) {
  return new Date(seconds * 1000).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export const round = (v, digits = 0) => (v == null ? null : Math.round(v * 10 ** digits) / 10 ** digits)
