import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { prefersReducedMotion } from '../../lib/motion'

const BUBBLE_AT_MS = 2400
const IDLE_AT_MS = 10000

// The forest plays as a looping video. Oli flies in and lands on the stump (oli-hello plays once), his drawn speech bubble
// appears at 2.4 s, and he swaps to the idle loop at 10 s. Reduced motion: still image, bubble at once.
export default function Hero() {
  const [reduce] = useState(prefersReducedMotion)
  const [src, setSrc] = useState(reduce ? '/oli-still.webp' : '/oli-hello.webp')
  const [talking, setTalking] = useState(reduce)
  const video = useRef()

  // Muted, looping, inline background. With reduced motion it stays paused on its poster.
  useEffect(() => {
    const v = video.current
    if (!v) return
    v.muted = true
    if (reduce) v.pause()
    else v.play().catch(() => { /* autoplay blocked: the poster shows instead */ })
  }, [reduce])

  useEffect(() => {
    if (reduce) return
    const a = setTimeout(() => setTalking(true), BUBBLE_AT_MS)
    const b = setTimeout(() => setSrc('/oli-idle.webp'), IDLE_AT_MS)
    return () => { clearTimeout(a); clearTimeout(b) }
  }, [reduce])

  return (
    <section className="hero" aria-label="Podium">
      <div className="hero-copy">
        <h1>Rehearse it out loud before it counts.</h1>
        <p>Oli plays the interviewer, investor, or opponent, then tells you the two things to fix before the real thing.</p>
        <div className="ctas">
          <Link className="btn primary" to="/practice">Start practicing</Link>
          <a className="link" href="#how">See how it works</a>
        </div>
      </div>
      <div className="art">
        <div className="scene" aria-hidden="true">
          <video ref={video} className="bg" src="/forest.mp4" poster="/forest-poster.webp"
                 muted loop playsInline autoPlay={!reduce} preload="auto" disablePictureInPicture tabIndex={-1} />
          <div className="oli"><img src={src} alt="" width="480" height="480" /></div>
          <div className={`say${talking ? ' on' : ''}`}>
            <svg className="shape" viewBox="0 0 220 104" preserveAspectRatio="none" aria-hidden="true">
              <path d="M14 3 C 70 0, 150 1, 206 3 C 214 4, 217 9, 217 17 L 217 72 C 217 80, 213 85, 205 86 L 112 87 L 96 102 L 92 87 L 15 86 C 7 85, 3 80, 3 72 L 3 17 C 3 9, 7 4, 14 3 Z" fill="#FFF8EE" stroke="#4A3527" strokeWidth="2.5" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
            <p>So, tell me about a time you disagreed with a teammate.</p>
          </div>
        </div>
      </div>
    </section>
  )
}
