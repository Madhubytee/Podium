import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useShell } from '../components/app/AppShell'
import Marked from '../components/app/Marked'
import { occasionFor } from '../config/occasions'
import { clock, plural } from '../lib/format'
import { startEyeContact } from '../lib/eyeContact'
import { extensionFor, getMedia, startAnswerAudio, startRecording } from '../lib/recorder'
import { countFillers, recentWpm, speak, speechSupported, startTranscriber } from '../lib/speech'

const SILENCE_END_MS = 2000 // a live answer ends after ~2 s of quiet (Done answering is the backup)
const MIN_ANSWER_MS = 3000

// /practice/takes/:id/session. The take written as a script: YOU (what you told Oli), OLI with his
// opening question, then the exchange as it happens. The full take records the whole time and
// uploads at the end; live mode also talks to Oli over the WebSocket.
export default function Session() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { refresh, setCrumb } = useShell()
  const [take, setTake] = useState(null)
  const [rehearsal, setRehearsal] = useState(null)
  const [camera, setCamera] = useState(true)
  const [phase, setPhase] = useState('ready') // ready | asking | countdown | running | uploading
  const [count, setCount] = useState(3)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [transcript, setTranscript] = useState({ finalText: '', interim: '', words: [] })
  const [eye, setEye] = useState(null)
  // live mode
  const [turns, setTurns] = useState([]) // [{ who: 'oli'|'you', text, open? , from? }]
  const [oliState, setOliState] = useState('waiting') // waiting | talking | listening | thinking | done
  const [hint, setHint] = useState(null)

  const videoRef = useRef()
  const r = useRef({}).current // mutable session state the callbacks share

  useEffect(() => {
    let cancelled = false
    api.getTake(id).then(async (t) => {
      if (t.status !== 'recording') { navigate(`/practice/takes/${id}`, { replace: true }); return }
      const reh = await api.getRehearsal(t.rehearsal_id)
      if (cancelled) return
      setTake(t)
      setRehearsal(reh)
      setCrumb({ title: reh.title, sub: `Take ${t.number}`, rehearsalId: reh.id })
    }).catch((e) => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [id, navigate, setCrumb])

  // Clean up everything when leaving the page.
  useEffect(() => () => {
    clearInterval(r.countdown)
    r.stopAll?.()
    r.stream?.getTracks().forEach((t) => t.stop())
    window.speechSynthesis?.cancel()
  }, [r])

  const live = take?.mode === 'live'
  const now = () => (performance.now() - r.recStart) / 1000

  // --- start: mic (and camera), 3 2 1, record ---------------------------------

  const begin = async () => {
    setError(null)
    setNotice(null)
    setPhase('asking')
    let withCamera = camera
    try {
      r.stream = await getMedia(withCamera)
    } catch {
      if (withCamera) {
        try {
          r.stream = await getMedia(false)
          withCamera = false
          setCamera(false)
          setNotice("Couldn't use your camera, so this take is audio only.")
        } catch { /* falls through */ }
      }
      if (!r.stream) {
        setPhase('ready')
        setError('Podium needs your microphone. Allow access in your browser, then try again.')
        return
      }
    }
    r.camera = withCamera
    if (videoRef.current) videoRef.current.srcObject = withCamera ? r.stream : null
    setPhase('countdown')
    setCount(3)
    let n = 3
    r.countdown = setInterval(() => {
      n -= 1
      setCount(n)
      if (n === 0) { clearInterval(r.countdown); run() }
    }, 800)
  }

  const run = () => {
    setPhase('running')
    r.recorder = startRecording(r.stream)
    r.recStart = performance.now()
    const timer = setInterval(() => setElapsed(now()), 250)
    r.transcriber = startTranscriber(setTranscript)
    const stopEye = r.camera && videoRef.current ? startEyeContact(videoRef.current, setEye) : () => {}
    const stopVad = watchVoice()
    r.stopAll = () => {
      r.stopAll = null // runs once: finishing and leaving the page both call it
      clearInterval(timer)
      r.transcriber?.stop()
      stopEye()
      stopVad()
      r.ws?.close()
      r.stopAnswer?.()
    }
    if (take.mode === 'live') connectOli()
  }

  // --- live conversation with Oli --------------------------------------------

  const connectOli = async () => {
    const ws = await api.liveSocket(take.id)
    if (r.finishing || !r.stopAll) { ws.close(); return }
    r.ws = ws
    ws.onopen = () => { setOliState('thinking'); ws.send(JSON.stringify({ type: 'start' })) }
    ws.onerror = () => setError('Lost the connection to Oli. Keep going if you like; your take is still recording.')
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'oli') oliSays(msg)
      else if (msg.type === 'hint') setHint(msg.text)
      else if (msg.type === 'transcript') {
        // Whisper's version of the answer you just gave replaces the browser's draft.
        setTurns((ts) => {
          const i = ts.findLastIndex((t) => t.who === 'you')
          return i < 0 ? ts : ts.map((t, j) => (j === i ? { ...t, text: msg.text } : t))
        })
      } else if (msg.type === 'error') {
        setError(`Oli can't talk right now: ${msg.message} You can keep going; your take is still recording, and you'll get feedback when you finish.`)
        setOliState('waiting')
      }
    }
  }

  const oliSays = ({ turn_id: turnId, text, final }) => {
    setHint(null)
    setTurns((ts) => [...ts, { who: 'oli', text, final }])
    let start = null
    speak(text, {
      onStart: () => { start = now(); setOliState('talking') },
      onEnd: () => {
        if (r.ws?.readyState === 1) r.ws.send(JSON.stringify({ type: 'oli_spoken', turn_id: turnId, start: start ?? now(), end: now() }))
        if (final) { setOliState('done'); setTimeout(finish, 1200) } else beginAnswer()
      },
    })
  }

  const beginAnswer = () => {
    setOliState('listening')
    r.answerStart = now()
    r.answerTextStart = r.transcriber?.text().length ?? 0
    r.heardVoice = false
    setTurns((ts) => [...ts, { who: 'you', text: '', open: true, from: r.answerTextStart }])
    r.stopAnswer = startAnswerAudio(r.stream, (chunk) => r.ws?.readyState === 1 && r.ws.send(chunk))
  }

  const endAnswer = async (type = 'answer_done') => {
    if (!r.stopAnswer) return
    const stop = r.stopAnswer
    r.stopAnswer = null
    await stop()
    setOliState('thinking')
    const draft = (r.transcriber?.text() ?? '').slice(r.answerTextStart ?? 0).trim()
    setTurns((ts) => ts.map((t) => (t.open ? { who: 'you', text: type === 'skip' ? '' : draft, skipped: type === 'skip' } : t)))
    r.ws?.send(JSON.stringify(type === 'skip' ? { type } : { type, start: r.answerStart, end: now(), draft }))
  }

  // Voice activity on the mic: a live answer ends after a stretch of silence.
  const watchVoice = () => {
    const ctx = new AudioContext()
    const analyser = ctx.createAnalyser()
    analyser.fftSize = 1024
    ctx.createMediaStreamSource(r.stream).connect(analyser)
    const buf = new Float32Array(analyser.fftSize)
    let lastVoice = performance.now()
    const timer = setInterval(() => {
      analyser.getFloatTimeDomainData(buf)
      const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length)
      const t = performance.now()
      if (rms > 0.02) { lastVoice = t; r.heardVoice = true }
      const answering = r.stopAnswer && (t - r.recStart) / 1000 - r.answerStart > MIN_ANSWER_MS / 1000
      if (answering && r.heardVoice && t - lastVoice > SILENCE_END_MS) endAnswer()
    }, 100)
    return () => { clearInterval(timer); if (ctx.state !== 'closed') ctx.close() }
  }

  // --- finishing -------------------------------------------------------------

  const finish = async () => {
    if (r.finishing) return
    r.finishing = true
    setPhase('uploading')
    window.speechSynthesis?.cancel()
    if (r.ws?.readyState === 1) r.ws.send(JSON.stringify({ type: 'end' }))
    r.stopAll?.()
    try {
      const blob = r.blob ?? await r.recorder.stop()
      r.blob = blob
      r.stream?.getTracks().forEach((t) => t.stop())
      await api.uploadTake(take.id, blob, `take${extensionFor(r.recorder.mimeType)}`)
      refresh()
      navigate(`/practice/takes/${take.id}`)
    } catch (e) {
      setError(`Upload failed: ${e.message}. Your recording is still here; try sending it again.`)
      r.finishing = false
      setPhase('failed')
    }
  }

  // --- render ----------------------------------------------------------------

  if (!take || !rehearsal) {
    return (
      <div className="body"><div className="session">
        {error ? <p className="err" role="alert">{error}</p> : <p className="muted">Getting the script ready...</p>}
      </div></div>
    )
  }

  const occ = occasionFor(rehearsal.occasion)
  const limit = rehearsal.time_limit ? rehearsal.time_limit * 60 : null
  const running = phase === 'running'
  const started = running || phase === 'uploading' || phase === 'failed'
  const meta = [
    occ.name,
    rehearsal.time_limit && plural(rehearsal.time_limit, 'minute'),
    rehearsal.audience && `talking to ${rehearsal.audience}`,
    ...(rehearsal.files ?? []).map((f) => f.filename),
  ].filter(Boolean).join(' · ')

  // live meters (a guide only; the real numbers come from the server afterwards)
  const wpm = recentWpm(transcript.words)
  const fullText = `${transcript.finalText} ${transcript.interim}`.trim()
  const fillersPerMin = Math.round((countFillers(fullText) / Math.max(elapsed / 60, 0.25)) * 10) / 10
  const liveText = (from) => transcript.finalText.slice(from).trim()

  // Oli's first line carries his picture; later lines are plain script lines (one Oli per screen).
  const first = turns[0]?.who === 'oli' ? turns[0] : null
  const rest = first ? turns.slice(1) : turns
  const lastOli = turns.findLastIndex((t) => t.who === 'oli')
  const firstQ = first?.text
    ?? (live && running && !error ? (oliState === 'waiting' ? 'Connecting...' : 'Hmm, let me think of a good first question...') : occ.q)

  const status = {
    ready: live ? 'Answer out loud when you are ready' : 'Record when you are ready',
    asking: 'Allow your microphone in the browser prompt',
    countdown: `Starting in ${count || 'now'}`,
    uploading: 'Sending your take to Oli...',
    failed: 'Your take did not send',
  }[phase] ?? (!live ? 'Recording. Give it start to finish.'
    : { talking: 'Oli is talking', listening: 'Your turn. Oli is listening.', thinking: 'Oli is thinking', done: "That's a wrap", waiting: 'Recording' }[oliState])

  return (
    <div className="body">
      <div className="session">
        <div className="line">
          <div className="cue">YOU</div>
          <p className="you">{rehearsal.details || `Practicing a ${occ.name.toLowerCase()}.`}</p>
          <div className="meta">{meta}</div>
        </div>

        <div className="line oli oli-line">
          <img src={occ.img} alt="Oli" width="92" height="92" />
          <div>
            <div className="cue">OLI</div>
            <p className="lead">{occ.lead}</p>
            <p className={lastOli <= 0 ? 'q' : 'said'}>{firstQ}</p>
          </div>
        </div>

        {live && rest.map((t, i) => {
          const idx = i + (first ? 1 : 0)
          if (t.who === 'oli') {
            return (
              <div className="line oli" key={idx}>
                <div className="cue">OLI {!t.final && <small>(following up)</small>}</div>
                <p className={idx === lastOli ? 'q' : 'said'}>{t.text}</p>
              </div>
            )
          }
          return (
            <div className="line" key={idx}>
              <div className="cue">YOU {t.open && <small>(answering)</small>}</div>
              <p className="you">
                {t.open ? <Marked text={liveText(t.from)} interim={transcript.interim} />
                  : t.skipped ? <span className="muted">(skipped)</span>
                    : t.text ? <Marked text={t.text} /> : <span className="muted">(no words caught)</span>}
              </p>
            </div>
          )
        })}

        {hint && (
          <div className="margin-note" role="status">
            <div className="cue">HINT</div>
            <p>{hint}</p>
          </div>
        )}

        {!live && started && (
          <div className="line" aria-live="polite">
            <div className="cue">YOU {running && <small>(recording)</small>}</div>
            <p className="you">
              {transcript.finalText || transcript.interim
                ? <Marked text={transcript.finalText} interim={transcript.interim} />
                : <span className="muted">{speechSupported() ? 'Your words show up here as you talk.' : 'The live transcript works in Chrome or Edge. Your full transcript will be in the report.'}</span>}
            </p>
          </div>
        )}

        {error && <p className="err" role="alert">{error}</p>}
        {notice && <p className="field-note">{notice}</p>}

        <div className="rec">
          <video ref={videoRef} className="preview" autoPlay muted playsInline
                 hidden={!(r.camera && camera) || phase === 'ready' || phase === 'asking'} />
          <div className="chk">
            <b>{status}</b>
            {phase === 'ready' && (
              <>
                Your browser will ask for your microphone. The camera is optional.{' '}
                <button type="button" className="text-btn inline" onClick={() => setCamera(!camera)} aria-pressed={camera}>
                  {camera ? 'Camera on, turn it off' : 'Audio only, turn camera on'}
                </button>
              </>
            )}
            {phase === 'countdown' && 'Look up, breathe, and start when it says go.'}
            {running && live && oliState === 'listening' && 'Pause for two seconds when you finish and Oli will reply.'}
            {running && !live && "Press I'm done when you finish."}
          </div>
          <span className={`timer${limit && elapsed > limit ? ' over' : ''}`}>
            {phase === 'countdown' ? count || 'Go' : clock(elapsed)}{' '}
            {limit && phase !== 'countdown' && <span>/ {clock(limit)}</span>}
          </span>
          {(phase === 'ready' || phase === 'asking' || phase === 'countdown') && (
            <button className="btn primary" type="button" onClick={begin} disabled={phase !== 'ready'}>
              {live ? 'Answer out loud' : 'Start recording'}
            </button>
          )}
          {running && <button className="btn primary" type="button" onClick={finish}>I'm done, how'd I do?</button>}
          {phase === 'failed' && <button className="btn primary" type="button" onClick={finish}>Send it again</button>}
        </div>

        {running && live && (
          <div className="controls">
            <button type="button" className="text-btn" disabled={oliState !== 'listening'} onClick={() => endAnswer()}>Done answering</button>
            <button type="button" className="text-btn" disabled={lastOli < 0 || oliState === 'talking'} onClick={() => speak(turns[lastOli].text)}>Repeat the question</button>
            <button type="button" className="text-btn" disabled={oliState !== 'listening'} onClick={() => r.ws?.send(JSON.stringify({ type: 'hint' }))}>Give me a hint</button>
            <button type="button" className="text-btn mute" disabled={oliState !== 'listening'} onClick={() => endAnswer('skip')}>Skip this one</button>
          </div>
        )}

        {running && (
          <div className="stats live-stats" aria-label="Live meters">
            <div className={`stat${wpm && (wpm > 170 || wpm < 110) ? ' flag' : ''}`}><b>{wpm ?? '...'} <small>wpm</small></b><span>Pace, aim for 130 to 160</span></div>
            <div className={`stat${fillersPerMin > 5 ? ' flag' : ''}`}><b>{fillersPerMin} <small>/min</small></b><span>Filler words</span></div>
            <div className={`stat${eye != null && eye < 60 ? ' flag' : ''}`}><b>{!r.camera ? 'Off' : eye == null ? '...' : `${eye}%`}</b><span>Eye contact</span></div>
          </div>
        )}

        {phase === 'ready' && (
          <p className="fine">
            Your video is analyzed on our own server, never sent to a third party, and deleted after 30 days.
            {live && ' In live mode your answers are transcribed by OpenAI Whisper so Oli can reply.'}
          </p>
        )}
      </div>
    </div>
  )
}
