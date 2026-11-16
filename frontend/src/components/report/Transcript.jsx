import { Fragment } from 'react'

// The coach's marked up transcript: wavy tomato under fillers, dotted under hedges, unclear words
// muted, ‖ pauses in olive, and superscript numbers where each margin note's first moment starts.
//   words  report.transcript [{ text, start, end, tags[], pause_after? }]
//   marks  [{ n, start }] superscripts to place
export default function Transcript({ words, marks }) {
  // Each mark goes after the last word that starts at or before its moment (or on the first word).
  const after = new Map()
  for (const m of marks) {
    let i = words.findLastIndex((w) => w.start <= m.start + 0.05)
    if (i < 0) i = 0
    after.set(i, [...(after.get(i) ?? []), m.n])
  }

  return (
    <p className="transcript">
      {words.map((w, i) => {
        const cls = [
          w.tags.includes('filler') && 'um',
          w.tags.includes('hedge') && 'hedge',
          (w.tags.includes('unclear') || w.tags.includes('trailing')) && !w.tags.includes('filler') && 'unclear',
        ].filter(Boolean).join(' ')
        const pause = w.pause_after
        return (
          <Fragment key={i}>
            {cls ? <span className={cls}>{w.text}</span> : w.text}
            {after.get(i)?.map((n) => <span className="mk" key={n}>{n}</span>)}
            {' '}
            {pause && (
              <><span className="pause" title={pause.tags?.includes('mid_sentence') ? 'Pause in the middle of a sentence' : 'Pause'}>‖ {pause.duration.toFixed(1)}s</span>{' '}</>
            )}
          </Fragment>
        )
      })}
    </p>
  )
}
