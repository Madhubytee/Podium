import { Link } from 'react-router-dom'
import Wordmark from '../Wordmark'

export default function TopNav() {
  return (
    <header className="topnav">
      <div className="wrap">
        <Wordmark to="/" onClick={() => window.scrollTo(0, 0)} />
        <nav aria-label="Main">
          <a href="#how">How it works</a>
          <a href="#feedback">Feedback</a>
          <Link className="btn primary" to="/practice">Start practicing</Link>
        </nav>
      </div>
    </header>
  )
}
