import { Link } from 'react-router-dom'
import Wordmark from '../Wordmark'

// The scrolling sections below the hero. Copy is from the approved design; the feedback
// section is a static example report, the real one is pages/Report.jsx.

export function HowItWorks() {
  return (
    <section className="band" id="how">
      <div className="wrap">
        <p className="kicker">How a rehearsal goes</p>
        <h2>Pick the moment, say it out loud, fix two things.</h2>
        <div className="flow">
          <div className="moment">
            <h3>You pick what's coming up</h3>
            <p>Add your resume, slides, or script so Oli knows the details.</p>
            <ul className="picks">
              <li className="sel">Job interview<em>Oli asks</em></li>
              <li>Pitch<em>Oli pushes back</em></li>
              <li>Presentation<em>You record</em></li>
              <li>Speech or toast<em>You record</em></li>
              <li>Debate<em>Oli argues</em></li>
            </ul>
          </div>
          <div className="moment">
            <h3>Oli plays the part</h3>
            <p>He asks out loud and follows up when an answer is vague.</p>
            <div className="script">
              <span className="cue oli">OLI</span>
              <p>Why this internship, and why now?</p>
              <span className="cue">YOU</span>
              <p><span className="um">Um</span>, so I've been building speaking tools, <span className="um">like</span>, all year...</p>
              <span className="cue oli">OLI <small>(following up)</small></span>
              <p>What did one of those tools actually change for users?</p>
            </div>
          </div>
          <div className="moment">
            <h3>You get two fixes, not twenty</h3>
            <p>The most important issues first, each with a clip of the moment.</p>
            <ol className="fixes">
              <li><span className="n">1</span><div><b>Slow down your opening</b><span>182 words per minute in the first 30 seconds.</span></div></li>
              <li><span className="n">2</span><div><b>Swap "um" for a pause</b><span>6 fillers per minute, mostly at the start of answers.</span></div></li>
            </ol>
          </div>
        </div>
      </div>
    </section>
  )
}

export function FeedbackSample() {
  return (
    <section className="band" id="feedback">
      <div className="wrap">
        <p className="kicker">Feedback</p>
        <h2>See exactly where it slipped.</h2>
        <p className="intro">Podium listens to your words and your voice, and watches eye contact and gestures if your camera is on. Then it marks up your answer the way a coach would.</p>
        <div className="markup">
          <div className="page-head"><b>TAKE 2 · SWE INTERNSHIP INTERVIEW</b><span>Example report</span></div>
          <p className="transcript">
            <span className="um">So</span>, on our capstone project, <span className="um">um</span>, a teammate wanted to rebuild the backend the week before the deadline. <span className="pause">‖ 3.4s</span><span className="mk">1</span> I, <span className="um">like</span>, didn't think we had time, so we compared both plans with our TA and kept the old backend. We shipped on time, and the TA used our plan as an example for the next class.<span className="mk">2</span>
          </p>
          <ol className="notes">
            <li><span className="n">1</span><b>You lost your place mid answer</b><p>A 3.4 second pause in the middle of a sentence. Anchor each answer to three words: situation, action, result.</p><a className="clip" href="#feedback">Watch the moment, 0:42</a></li>
            <li><span className="n">2</span><b>Your answer ran 2 minutes 40</b><p>Interview answers land best under two minutes. Lead with the result next time.</p><a className="clip" href="#feedback">Watch the moment, 1:10</a></li>
            <li className="good"><span className="n">✓</span><b>Keep doing this</b><p>Strong eye contact while you gave your example.</p></li>
          </ol>
          <div className="stats">
            <div className="stat flag"><b>182 <small>wpm</small></b><span>Pace, aim for 130 to 160</span></div>
            <div className="stat"><b>6 <small>/min</small></b><span>Filler words</span></div>
            <div className="stat"><b>71%</b><span>Eye contact</span></div>
            <div className="stat"><b>2:40</b><span>Answer length</span></div>
          </div>
        </div>
      </div>
    </section>
  )
}

export function Trust() {
  return (
    <section className="band">
      <div className="wrap">
        <p className="kicker">Why you can trust it</p>
        <h2>Coaching rules written with real speaking experts.</h2>
        <div className="rules">
          <div>
            <p className="rule"><span className="w">IF</span>an interview answer runs past two minutes, <span className="w">THEN</span>suggest the STAR format and ending on the result.</p>
            <p className="rule-src">One of the 17 rules Oli follows, reviewed by our domain experts.</p>
          </div>
          <ul className="points">
            <li><b>Every tip shows its reason.</b><span>Tap "Why this feedback?" to see the rule and the moment it came from.</span></li>
            <li><b>Feedback depends on the occasion.</b><span>A pause that works in a toast reads as lost in an interview.</span></li>
            <li><b>It remembers your last take.</b><span>Oli tells you what improved before he gives you anything new.</span></li>
          </ul>
        </div>
      </div>
    </section>
  )
}

export function FinalCall() {
  return (
    <section className="band final">
      <div className="wrap">
        <div className="with">
          <img src="/oli-pitch.webp" alt="" width="110" height="110" />
          <h2>Your next big moment is coming. Practice it first.</h2>
        </div>
        <Link className="btn primary" to="/practice">Start practicing</Link>
      </div>
    </section>
  )
}

export function Footer() {
  return (
    <footer>
      <div className="wrap">
        <Wordmark style={{ fontSize: 18 }} />
        <span>Group 21 · University of Florida</span>
      </div>
    </footer>
  )
}
