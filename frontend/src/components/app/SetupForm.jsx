import { useRef, useState } from 'react'
import { ACCEPTED_FILES, OCCASIONS, acceptedFile, minutesOf } from '../../config/occasions'

const ClipIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true"><path d="M21 12.5l-8.5 8.5a6 6 0 0 1-8.5-8.5L13 3.5a4 4 0 0 1 5.7 5.7l-8.6 8.6a2 2 0 0 1-2.8-2.8L15 7.3" /></svg>
)

// "What are we practicing?" The form only collects; onStart / onUpload (from the page) talk to the API.
//   onStart({ occasion, mode, details, audience, time_limit, files })
//   onUpload({ ...same, recording: File })
export default function SetupForm({ busy, error, onStart, onUpload }) {
  const [occ, setOcc] = useState(OCCASIONS[0])
  const [time, setTime] = useState(OCCASIONS[0].time[OCCASIONS[0].t])
  const [aud, setAud] = useState(OCCASIONS[0].aud[0])
  const [mode, setMode] = useState(OCCASIONS[0].live ? 'live' : 'record')
  const [details, setDetails] = useState('')
  const [files, setFiles] = useState([])
  const [skipped, setSkipped] = useState([])
  const [over, setOver] = useState(false)
  const tabs = useRef()
  const recordingInput = useRef()

  const pick = (o) => {
    setOcc(o)
    setTime(o.time[o.t])
    setAud(o.aud[0])
    setMode(o.live ? 'live' : 'record')
  }

  const onTabKey = (e) => {
    const n = OCCASIONS.length
    let i = OCCASIONS.indexOf(occ)
    if (e.key === 'ArrowRight') i = (i + 1) % n
    else if (e.key === 'ArrowLeft') i = (i - 1 + n) % n
    else return
    e.preventDefault()
    pick(OCCASIONS[i])
    tabs.current.children[i].focus()
  }

  // Files from the picker or dropped on the notes. Oli can only read pdf, docx, pptx, txt, md.
  const addFiles = (list) => {
    const incoming = Array.from(list)
    const ok = incoming.filter(acceptedFile)
    setSkipped(incoming.filter((f) => !acceptedFile(f)).map((f) => f.name))
    setFiles((cur) => [...cur, ...ok.filter((f) => !cur.some((x) => x.name === f.name))])
  }

  const drag = (on) => (e) => { e.preventDefault(); setOver(on) }

  const values = () => ({
    occasion: occ.id,
    mode,
    details: details.trim() || null,
    audience: aud,
    time_limit: minutesOf(time),
    files,
  })

  const submit = (e) => {
    e.preventDefault()
    if (!busy) onStart(values())
  }

  return (
    <form className="setup" noValidate onSubmit={submit}>
      <div className="ask">
        <img src={occ.img} alt="Oli" width="104" height="104" />
        <div>
          <h1>What are we practicing?</h1>
          <p>{occ.sub}</p>
        </div>
      </div>

      <div>
        <span className="label" id="occLabel">The occasion</span>
        <div className="tabs" role="radiogroup" aria-labelledby="occLabel" ref={tabs} onKeyDown={onTabKey}>
          {OCCASIONS.map((o) => (
            <button key={o.id} type="button" className="occ" role="radio" aria-checked={o === occ}
                    tabIndex={o === occ ? 0 : -1} onClick={() => pick(o)}>
              {o.name}
            </button>
          ))}
        </div>
      </div>

      <p className="madlib">
        It runs about <label className="sr" htmlFor="time">Length</label>
        <select id="time" value={time} onChange={(e) => setTime(e.target.value)}>
          {occ.time.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        {' '}and I'm talking to <label className="sr" htmlFor="aud">Audience</label>
        <select id="aud" value={aud} onChange={(e) => setAud(e.target.value)}>
          {occ.aud.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>.
      </p>

      <div>
        <label className="label" htmlFor="details">Notes for Oli <small>optional, but his questions get better</small></label>
        <div className={`notes-in${over ? ' over' : ''}`}
             onDragEnter={drag(true)} onDragOver={drag(true)} onDragLeave={drag(false)}
             onDrop={(e) => { drag(false)(e); addFiles(e.dataTransfer?.files ?? []) }}>
          <textarea id="details" rows="3" placeholder={occ.ph} value={details} onChange={(e) => setDetails(e.target.value)} />
        </div>
        <div className="attach-row">
          <label className="attach" htmlFor="files">
            <ClipIcon />
            Attach files
            <input className="sr" type="file" id="files" multiple accept={ACCEPTED_FILES}
                   onChange={(e) => { addFiles(e.target.files); e.target.value = '' }} />
          </label>
          {files.length === 0 && <span className="attach-hint">{occ.files}</span>}
          <span aria-label="Attached files" style={{ display: 'contents' }}>
            {files.map((f) => (
              <span className="chip" key={f.name}>
                <span>{f.name}</span>
                <button type="button" aria-label={`Remove ${f.name}`} onClick={() => setFiles(files.filter((x) => x !== f))}>
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
                </button>
              </span>
            ))}
          </span>
        </div>
        {skipped.length > 0 && (
          <p className="field-note" role="status">
            Oli can't read {skipped.join(', ')}. He reads PDF, Word (.docx), PowerPoint (.pptx), and text files.
          </p>
        )}
      </div>

      <fieldset className="modes">
        <legend className="label">How you want to practice</legend>
        <label className="mode">
          <input type="radio" name="mode" value="live" checked={mode === 'live'} onChange={() => setMode('live')} />
          <span><b>Talk it through with Oli</b><span className="d">{occ.role}</span></span>
        </label>
        <label className="mode">
          <input type="radio" name="mode" value="record" checked={mode === 'record'} onChange={() => setMode('record')} />
          <span><b>Record the whole thing</b><span className="d">Give it start to finish. Feedback comes at the end.</span></span>
        </label>
      </fieldset>

      <div className="start-row">
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Setting up...' : mode === 'record' ? 'Start recording' : occ.start}
        </button>
        <span>Uses your microphone. Camera is optional.</span>
        <button type="button" className="text-btn" disabled={busy} onClick={() => recordingInput.current.click()}>
          Or upload a recording
        </button>
        <input ref={recordingInput} className="sr" type="file" accept="video/*,audio/*" tabIndex={-1} aria-hidden="true"
               onChange={(e) => { const f = e.target.files[0]; e.target.value = ''; if (f) onUpload({ ...values(), recording: f }) }} />
      </div>

      {error && <p className="err" role="alert">{error}</p>}
    </form>
  )
}
