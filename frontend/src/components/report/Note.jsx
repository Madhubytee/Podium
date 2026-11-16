import { useState } from 'react'
import { api } from '../../api'
import { clock } from '../../lib/format'

const SHOW_FACTS = 6

// One margin note: what Oli noticed, why, what to do, a clip of the moment, and
// "Why this feedback?" which shows the rule's test and the facts it came from.
export default function Note({ n, d, takeId, playback }) {
  const [clip, setClip] = useState(null)
  const [why, setWhy] = useState(false)
  const [facts, setFacts] = useState(null)
  const [factsError, setFactsError] = useState(null)
  const [clipError, setClipError] = useState(false)
  const moment = d.moments?.[0]

  const toggleWhy = () => {
    const next = !why
    setWhy(next)
    if (next && !facts && d.fact_ids?.length) {
      api.facts(takeId, d.fact_ids.slice(0, 40))
        .then(setFacts)
        .catch(() => setFactsError("Couldn't load the facts behind this one."))
    }
  }

  return (
    <li>
      <span className="n">{n}</span><b>{d.name}</b>
      <p>{d.why}</p>
      <p className="tip"><span className="tip-k">Try this</span>{d.tip}</p>
      {d.drill && <p className="drill"><span className="tip-k">Drill</span>{d.drill}</p>}
      <div className="note-actions">
        {playback && moment && (
          <button type="button" className="clip" onClick={() => setClip(clip ? null : moment)} aria-expanded={!!clip}>
            {clip ? 'Hide the clip' : `Watch the moment, ${clock(moment.start)}`}
          </button>
        )}
        <button type="button" className="clip quiet" onClick={toggleWhy} aria-expanded={why}>Why this feedback?</button>
      </div>
      {clip && (clipError
        ? <p className="muted clip-missing">This clip isn't available anymore.</p>
        : <video className="clip-video" controls autoPlay playsInline onError={() => setClipError(true)}
                 src={api.clipUrl(takeId, Math.max(0, clip.start - 1).toFixed(2), (clip.end + 1).toFixed(2))} />
      )}
      {why && (
        <div className="why">
          {d.explanation?.map((e) => <code key={e}>{e}</code>)}
          {factsError && <p className="muted">{factsError}</p>}
          {facts && (
            <ul className="leaders small">
              {facts.slice(0, SHOW_FACTS).map((f) => (
                <li key={f.id}>
                  {String(f.name).replaceAll('_', ' ')}
                  <em>{typeof f.value === 'number' ? Math.round(f.value * 10) / 10 : String(f.value)}{f.start != null && ` at ${clock(f.start)}`}</em>
                </li>
              ))}
            </ul>
          )}
          {facts?.length > SHOW_FACTS && <p className="muted more">and {facts.length - SHOW_FACTS} more like these</p>}
        </div>
      )}
    </li>
  )
}
