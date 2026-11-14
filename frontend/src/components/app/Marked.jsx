import { isFiller } from '../../lib/speech'

// Live transcript text with the coach's wavy mark under sound fillers (um, uh, er...).
export default function Marked({ text, interim }) {
  const words = (text || '').split(/\s+/).filter(Boolean)
  return (
    <>
      {words.map((w, i) => (
        <span key={i}>{isFiller(w) ? <span className="um">{w}</span> : w}{' '}</span>
      ))}
      {interim && <span className="interim">{interim}</span>}
    </>
  )
}
