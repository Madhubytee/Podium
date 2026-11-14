import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useShell } from '../components/app/AppShell'
import SetupForm from '../components/app/SetupForm'

// /practice: the setup. Creates the rehearsal, uploads attached files, creates take 1,
// then goes to the session (or straight to the report for an uploaded recording).
export default function NewRehearsal() {
  const { refresh, setCrumb } = useShell()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // If a step fails after the rehearsal exists, a retry reuses it instead of making a duplicate.
  const made = useRef(null)

  useEffect(() => { setCrumb({ title: 'New rehearsal' }) }, [setCrumb])

  const prepare = async ({ occasion, mode, details, audience, time_limit, files }) => {
    const key = JSON.stringify({ occasion, mode, details, audience, time_limit })
    if (made.current?.key !== key) {
      const rehearsal = await api.createRehearsal({ occasion, mode, details, audience, time_limit })
      made.current = { key, id: rehearsal.id, uploaded: new Set() }
      refresh()
    }
    const rid = made.current.id
    const fresh = files.filter((f) => !made.current.uploaded.has(f.name))
    if (fresh.length) {
      try {
        await api.uploadFiles(rid, fresh)
      } catch (e) {
        throw new Error(`Couldn't attach your files: ${e.message}`)
      }
      fresh.forEach((f) => made.current.uploaded.add(f.name))
    }
    const take = await api.createTake(rid, mode)
    made.current = null
    refresh()
    return take
  }

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e.message || 'Something went wrong. Try again.')
      setBusy(false)
    }
  }

  const start = (values) => run(async () => {
    const take = await prepare(values)
    navigate(`/practice/takes/${take.id}/session`)
  })

  const upload = ({ recording, ...values }) => run(async () => {
    const take = await prepare({ ...values, mode: 'upload' })
    await api.uploadTake(take.id, recording, recording.name)
    refresh()
    navigate(`/practice/takes/${take.id}`)
  })

  return (
    <div className="body">
      <SetupForm busy={busy} error={error} onStart={start} onUpload={upload} />
    </div>
  )
}
