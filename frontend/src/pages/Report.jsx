import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useShell } from '../components/app/AppShell'
import Note from '../components/report/Note'
import PaceChart from '../components/report/PaceChart'
import Transcript from '../components/report/Transcript'
import { occasionFor } from '../config/occasions'
import { clock, round } from '../lib/format'

const POLL_MS = 2000
const STEPS = [
  ['audio', 'Pulling out the audio'],
  ['transcript', 'Writing down what you said'],
  ['frames', 'Watching your delivery'],
  ['playback', 'Cutting the playback'],
  ['analyzing', 'Measuring pace, fillers, and pauses'],
  ['reasoning', 'Checking the coaching rules'],
  ['report', 'Writing your notes'],
  ['saving', 'Saving your take'],
]

// /practice/takes/:id. Waits for the analysis, then shows the take as a coach's marked up page.
export default function Report() {
  const { id } = useParams()
  const { refresh, setCrumb } = useShell()
  const [take, setTake] = useState(null)
  const [rehearsal, setRehearsal] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer
    let wasProcessing = false
    setTake(null)
    setError(null)
    const load = () => api.getTake(id).then((t) => {
      if (cancelled) return
      setTake(t)
      if (t.status === 'processing' || (t.status === 'recording' && wasProcessing)) {
        wasProcessing = true
        timer = setTimeout(load, POLL_MS)
      } else if (wasProcessing) refresh() // sidebar picks up the new score
    }).catch((e) => !cancelled && setError(e.message))
    load()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [id, refresh])

  const rehearsalId = take?.rehearsal_id
  useEffect(() => {
    if (!rehearsalId) return
    api.getRehearsal(rehearsalId).then(setRehearsal).catch(() => {})
  }, [rehearsalId])

  useEffect(() => {
    if (take && rehearsal) setCrumb({ title: rehearsal.title, sub: `Take ${take.number}`, rehearsalId: rehearsal.id })
  }, [take, rehearsal, setCrumb])

  if (error) return <div className="body"><div className="report"><p className="err" role="alert">{error}</p></div></div>
  if (!take || !rehearsal) return <div className="body"><div className="report"><p className="muted">Finding your take...</p></div></div>

  const occ = occasionFor(rehearsal.occasion)
  if (take.status === 'recording') return <NotRecorded take={take} occ={occ} />
  if (take.status === 'processing') return <Processing take={take} occ={occ} />
  if (take.status === 'failed') return <Failed take={take} rehearsal={rehearsal} occ={occ} />
  return <Finished take={take} rehearsal={rehearsal} occ={occ} />
}

function Head({ occ, kicker, title, children }) {
  return (
    <div className="ask report-head">
      <img src={occ.img} alt="Oli" width="104" height="104" />
      <div>
        <p className="kicker">{kicker}</p>
        <h1>{title}</h1>
        {children}
      </div>
    </div>
  )
}

function NotRecorded({ take, occ }) {
  return (
    <div className="body"><div className="report">
      <Head occ={occ} kicker={`Take ${take.number} · ${occ.name}`} title="This take hasn't been recorded yet.">
        <p>Record it and Oli will mark it up here.</p>
      </Head>
      <div className="start-row"><Link className="btn primary" to={`/practice/takes/${take.id}/session`}>Record this take</Link></div>
    </div></div>
  )
}

function Processing({ take, occ }) {
  const at = STEPS.findIndex(([k]) => k === take.step)
  return (
    <div className="body"><div className="report narrow">
      <Head occ={occ} kicker={`Take ${take.number} · ${occ.name}`} title="Oli is going over your take.">
        <p>This usually takes under a minute. You can leave and come back; it'll be here.</p>
      </Head>
      <ul className="picks steps" aria-live="polite">
        {STEPS.map(([k, label], i) => (
          <li key={k} className={i === at ? 'sel' : i < at ? 'done' : ''}>
            {label}<em>{i < at ? 'done' : i === at ? 'now' : ''}</em>
          </li>
        ))}
      </ul>
    </div></div>
  )
}

function TryAgain({ rehearsal, take, label = 'Try again' }) {
  const navigate = useNavigate()
  const { refresh } = useShell()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const go = async () => {
    setBusy(true)
    setError(null)
    try {
      const mode = take?.mode && take.mode !== 'upload' ? take.mode : (rehearsal.mode === 'upload' ? 'record' : rehearsal.mode)
      const next = await api.createTake(rehearsal.id, mode)
      refresh()
      navigate(`/practice/takes/${next.id}/session`)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }
  return (
    <>
      <button className="btn primary" type="button" onClick={go} disabled={busy}>{busy ? 'Setting up...' : label}</button>
      {error && <p className="err" role="alert">{error}</p>}
    </>
  )
}

function Failed({ take, rehearsal, occ }) {
  return (
    <div className="body"><div className="report narrow">
      <Head occ={occ} kicker={`Take ${take.number} · ${occ.name}`} title="Oli couldn't finish this one.">
        <p>Something went wrong while he was going over your take.</p>
      </Head>
      {take.error && <p className="err">{take.error}</p>}
      <div className="start-row">
        <TryAgain rehearsal={rehearsal} take={take} label="Record it again" />
        <Link className="link" to={`/practice/rehearsals/${rehearsal.id}`}>All takes</Link>
      </div>
    </div></div>
  )
}

const STAR = ['situation', 'task', 'action', 'result']

function Finished({ take, rehearsal, occ }) {
  const rep = take.report
  const s = rep.summary ?? {}
  const eye = rep.charts?.eye_contact?.pct ?? s.eye_contact_pct
  const notes = [...(rep.focus ?? []), ...(rep.secondary ?? [])]
  const marks = notes.map((d, i) => d.moments?.[0] && { n: i + 1, start: d.moments[0].start }).filter(Boolean)
  const strengths = [rep.strength, ...(rep.other_strengths ?? [])].filter(Boolean)
  const fillers = Object.entries(rep.charts?.fillers_by_word ?? {}).sort((a, b) => b[1] - a[1])
  const pace = rep.charts?.pace ?? []
  const pg = rep.progress

  return (
    <div className="body"><div className="report">
      <Head occ={occ} kicker={`Take ${take.number} · ${occ.name}`} title={rep.headline} />

      {pg && (
        <section className="since">
          <p className="label">Since take {pg.previous_take}
            <small>{pg.score_change > 0 ? `up ${pg.score_change} points` : pg.score_change < 0 ? `down ${-pg.score_change} points` : 'same score'}</small>
          </p>
          <ul className="leaders">
            {pg.metrics?.map((m) => (
              <li key={m.label} className={m.improvement_pct > 0 ? 'better' : m.improvement_pct < 0 ? 'worse' : ''}>
                {m.label}
                <em>{fmtMetric(m.before)} to {fmtMetric(m.after)}{m.improvement_pct != null && `, ${m.improvement_pct > 0 ? 'better' : m.improvement_pct < 0 ? 'worse' : 'same'}${m.improvement_pct ? ` by ${Math.abs(Math.round(m.improvement_pct))}%` : ''}`}</em>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="stats five">
        <div className="stat"><b>{rep.score} <small>/100</small></b><span>Score</span></div>
        <div className={`stat${s.pace_wpm > 170 || s.pace_wpm < 110 ? ' flag' : ''}`}><b>{round(s.pace_wpm) ?? '...'} <small>wpm</small></b><span>Pace, aim for 130 to 160</span></div>
        <div className={`stat${s.filler_per_min > 5 ? ' flag' : ''}`}><b>{round(s.filler_per_min, 1) ?? '...'} <small>/min</small></b><span>Filler words</span></div>
        <div className={`stat${eye != null && eye < 60 ? ' flag' : ''}`}><b>{rep.camera === 'off' || eye == null ? 'Off' : `${Math.round(eye)}%`}</b><span>{rep.camera === 'off' ? 'Eye contact, camera off' : 'Eye contact'}</span></div>
        <div className="stat"><b>{clock(s.duration_s ?? take.duration)}</b><span>Length</span></div>
      </div>

      <div className="markup">
        <div className="page-head">
          <b>TAKE {take.number} · {rehearsal.title.toUpperCase()}</b>
          <span className="legend"><span className="um">filler</span> <span className="hedge">hedge</span> <span className="pause">‖ pause</span></span>
        </div>
        {rep.transcript?.length
          ? <Transcript words={rep.transcript} marks={marks} />
          : <p className="transcript muted">Oli didn't catch any words in this take.</p>}
        <ol className="notes">
          {notes.length === 0 && <li className="good"><span className="n">✓</span><b>Nothing to fix this time</b><p>None of the coaching rules flagged this take.</p></li>}
          {notes.map((d, i) => (
            <Note key={d.key} n={i + 1} d={d} takeId={take.id} playback={rep.playback} />
          ))}
          {strengths.map((d) => (
            <li className="good" key={d.key}><span className="n">✓</span><b>Keep doing this</b><p>{d.name}. {d.why}</p></li>
          ))}
        </ol>
      </div>

      {rep.answers?.length > 0 && (
        <section className="report-sec">
          <p className="kicker">Question by question</p>
          <div className="script answers">
            {rep.answers.map((a, i) => (
              <div key={i} className="answer">
                <span className="cue oli">OLI</span>
                <p>{a.question}</p>
                <span className="cue">YOU <small>{a.skipped ? '(skipped)' : `(${clock(a.duration_s)}, ${a.word_count} words)`}</small></span>
                {!a.skipped && occ.id === 'interview' && (
                  <p className="star">
                    {STAR.map((p) => <span key={p} className={a.star?.includes(p) ? 'has' : 'miss'}>{p}</span>)}
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="report-sec cols">
        {pace.length > 1 && (
          <div>
            <h2 className="sec-h">Pace over the take</h2>
            <p className="sec-sub">Words per minute. The shaded band is 130 to 160.</p>
            <PaceChart data={pace} />
          </div>
        )}
        <div>
          <h2 className="sec-h">The details</h2>
          <ul className="leaders">
            <li>Words<em>{s.word_count ?? '...'}</em></li>
            {fillers.map(([w, c]) => <li key={w}>"{w}"<em>{c}x</em></li>)}
            <li>Hedges, like "I think" or "maybe"<em>{s.hedge_count ?? 0}</em></li>
            <li>Pauses where you lost your place<em>{s.lost_place_pauses ?? 0}</em></li>
            {s.pitch_sd_hz != null && <li>Pitch variety<em>{Math.round(s.pitch_sd_hz)} Hz</em></li>}
            {s.clarity != null && <li>Words Oli heard clearly<em>{Math.round(s.clarity * 100)}%</em></li>}
          </ul>
        </div>
      </section>

      <div className="start-row report-actions">
        <TryAgain rehearsal={rehearsal} take={take} />
        <span>Oli will compare your next take with this one.</span>
        <Link className="link" to={`/practice/rehearsals/${rehearsal.id}`}>All takes</Link>
      </div>
    </div></div>
  )
}

function fmtMetric(v) {
  if (v == null) return '...'
  return typeof v === 'number' ? String(Math.round(v * 10) / 10) : String(v)
}
