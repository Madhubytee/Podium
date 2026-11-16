import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useShell } from '../components/app/AppShell'
import { occasionFor } from '../config/occasions'
import { clock, plural, round, shortDate } from '../lib/format'

const STATUS = { recording: 'Not recorded yet', processing: 'Oli is going over it', failed: "Didn't finish" }

// /practice/rehearsals/:id. The rehearsal, every take, progress across takes, and Try again.
export default function Rehearsal() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { refresh, setCrumb } = useShell()
  const [rehearsal, setRehearsal] = useState(null)
  const [progress, setProgress] = useState([])
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    setRehearsal(null)
    setError(null)
    Promise.all([api.getRehearsal(id), api.progress(id).catch(() => [])])
      .then(([r, p]) => {
        if (cancelled) return
        setRehearsal(r)
        setProgress(p)
        setCrumb({ title: r.title, sub: plural(r.takes.length, 'take'), rehearsalId: r.id })
      })
      .catch((e) => !cancelled && setError(e.message))
    return () => { cancelled = true }
  }, [id, setCrumb])

  if (error) return <div className="body"><div className="report narrow"><p className="err" role="alert">{error}</p><Link className="link" to="/practice">Start a new rehearsal</Link></div></div>
  if (!rehearsal) return <div className="body"><div className="report narrow"><p className="muted">Finding your rehearsal...</p></div></div>

  const occ = occasionFor(rehearsal.occasion)
  const takes = [...rehearsal.takes].sort((a, b) => b.number - a.number)
  const mode = rehearsal.mode === 'upload' ? 'record' : rehearsal.mode

  const tryAgain = async () => {
    setBusy(true)
    setError(null)
    try {
      const take = await api.createTake(rehearsal.id, mode)
      refresh()
      navigate(`/practice/takes/${take.id}/session`)
    } catch (e) {
      setError(e.message)
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!window.confirm(`Delete "${rehearsal.title}" and all of its takes?`)) return
    try {
      await api.deleteRehearsal(rehearsal.id)
      refresh()
      navigate('/practice')
    } catch (e) {
      setError(e.message)
    }
  }

  // The title is often the first line of the notes; don't say it twice.
  const showDetails = rehearsal.details && rehearsal.details.trim() !== rehearsal.title.trim()
  const meta = [
    occ.name,
    rehearsal.time_limit && plural(rehearsal.time_limit, 'minute'),
    rehearsal.audience && `talking to ${rehearsal.audience}`,
    `started ${shortDate(rehearsal.created_at)}`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="body">
      <div className="report narrow">
        <div className="ask report-head">
          <img src={occ.img} alt="Oli" width="104" height="104" />
          <div>
            <p className="kicker">{occ.name}</p>
            <h1>{rehearsal.title}</h1>
            <p>{meta}</p>
          </div>
        </div>

        {(showDetails || rehearsal.files.length > 0) && (
          <div className="line">
            <div className="cue">YOU</div>
            {showDetails && <p className="you">{rehearsal.details}</p>}
            {rehearsal.files.length > 0 && <div className="meta">{rehearsal.files.map((f) => f.filename).join(' · ')}</div>}
          </div>
        )}

        <section>
          <p className="label">Takes</p>
          {takes.length === 0 && <p className="muted">No takes yet.</p>}
          <ul className="take-list">
            {takes.map((t) => (
              <li key={t.id}>
                <Link to={t.status === 'recording' ? `/practice/takes/${t.id}/session` : `/practice/takes/${t.id}`}>
                  <span className="tn">Take {t.number}</span>
                  <em>
                    {t.status === 'done'
                      ? <><b>{t.score}</b> · {clock(t.duration)} · {shortDate(t.created_at)}</>
                      : STATUS[t.status] ?? t.status}
                  </em>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {progress.length > 1 && (
          <section>
            <p className="label">Across your takes</p>
            <div className="table-scroll">
              <table className="ruled">
                <thead>
                  <tr><th>Take</th><th>Score</th><th>Pace</th><th>Fillers</th><th>Eye contact</th></tr>
                </thead>
                <tbody>
                  {progress.map((p) => (
                    <tr key={p.take_id}>
                      <td><Link to={`/practice/takes/${p.take_id}`}>Take {p.take}</Link></td>
                      <td className="big">{p.score ?? '...'}</td>
                      <td>{p.pace_wpm != null ? `${round(p.pace_wpm)} wpm` : '...'}</td>
                      <td>{p.filler_per_min != null ? `${round(p.filler_per_min, 1)} /min` : '...'}</td>
                      <td>{p.eye_contact_pct != null ? `${Math.round(p.eye_contact_pct)}%` : 'Off'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {error && <p className="err" role="alert">{error}</p>}

        <div className="start-row report-actions">
          <button className="btn primary" type="button" onClick={tryAgain} disabled={busy}>{busy ? 'Setting up...' : 'Try again'}</button>
          <span>Take {(rehearsal.takes.length || 0) + 1}, {mode === 'live' ? 'talking it through with Oli' : 'recording the whole thing'}.</span>
          <button className="text-btn mute" type="button" onClick={remove}>Delete rehearsal</button>
        </div>
      </div>
    </div>
  )
}
