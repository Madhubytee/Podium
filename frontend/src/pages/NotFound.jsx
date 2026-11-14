import { Link } from 'react-router-dom'

export default function NotFound({ standalone = false }) {
  const inner = (
    <div className="setup">
      <div className="ask">
        <img src="/oli-debate.webp" alt="Oli" width="104" height="104" />
        <div>
          <h1>Hmm, nothing here.</h1>
          <p>That page doesn't exist. Let's get you back to practicing.</p>
        </div>
      </div>
      <div className="start-row"><Link className="btn primary" to="/practice">New rehearsal</Link><Link className="link" to="/">Home</Link></div>
    </div>
  )
  return <div className="body" style={standalone ? { minHeight: '100vh' } : undefined}>{inner}</div>
}
