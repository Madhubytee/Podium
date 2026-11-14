// Live transcript + gentle meters in the browser (Web Speech API, Chrome and Edge).
// The real numbers come from Whisper on the server afterwards; these are just a guide while you talk.

const SOUND_FILLERS = new Set(['um', 'umm', 'uh', 'uhh', 'uhm', 'er', 'erm', 'ah', 'hmm', 'mm'])
const PHRASE_FILLERS = ['you know', 'i mean', 'kind of', 'sort of', 'basically', 'actually', 'literally', 'like']

export const speechSupported = () => Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)

export function isFiller(word) {
  return SOUND_FILLERS.has(word.toLowerCase().replace(/[^a-z']/g, ''))
}

export function countFillers(text) {
  const lower = ` ${text.toLowerCase().replace(/[^a-z' ]/g, ' ')} `
  let n = lower.split(/\s+/).filter((w) => SOUND_FILLERS.has(w)).length
  for (const p of PHRASE_FILLERS) n += lower.split(` ${p} `).length - 1
  return n
}

// Calls onUpdate({ finalText, interim, words: [{text, t}] }) as you speak.
export function startTranscriber(onUpdate) {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!Rec) return { stop() {}, reset() {}, text: () => '' }

  const rec = new Rec()
  rec.continuous = true
  rec.interimResults = true
  rec.lang = 'en-US'
  let finalText = ''
  let words = []
  let stopped = false

  rec.onresult = (e) => {
    let interim = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i]
      if (r.isFinal) {
        const now = performance.now()
        r[0].transcript.trim().split(/\s+/).filter(Boolean).forEach((w) => words.push({ text: w, t: now }))
        finalText += ' ' + r[0].transcript.trim()
      } else {
        interim += r[0].transcript
      }
    }
    onUpdate({ finalText: finalText.trim(), interim: interim.trim(), words })
  }
  // Chrome ends recognition after silence; keep it going for the whole take.
  rec.onend = () => { if (!stopped) try { rec.start() } catch { /* already running */ } }
  rec.onerror = () => {}
  try { rec.start() } catch { /* ignore */ }

  return {
    stop() { stopped = true; rec.stop() },
    reset() { finalText = ''; words = []; onUpdate({ finalText: '', interim: '', words }) },
    text: () => finalText.trim(),
  }
}

// Words per minute over the last 20 seconds of speech.
export function recentWpm(words, windowMs = 20000) {
  const now = performance.now()
  const recent = words.filter((w) => now - w.t < windowMs)
  if (recent.length < 3) return null
  const span = Math.max((now - recent[0].t) / 60000, 5 / 60)
  return Math.round(recent.length / span)
}

// Oli's voice for the prototype: the browser's free speech synthesis.
export function speak(text, { onStart, onEnd } = {}) {
  if (!window.speechSynthesis) { onStart?.(); onEnd?.(); return }
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  const voices = window.speechSynthesis.getVoices()
  u.voice = voices.find((v) => /en-(US|GB)/.test(v.lang) && /Google|Samantha|Aria|Jenny|Guy/.test(v.name))
    || voices.find((v) => v.lang.startsWith('en')) || null
  u.rate = 1.02
  u.pitch = 1.15
  u.onstart = () => onStart?.()
  u.onend = () => onEnd?.()
  u.onerror = () => onEnd?.()
  window.speechSynthesis.speak(u)
}
