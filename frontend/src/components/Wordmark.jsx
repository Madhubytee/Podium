import { Link } from 'react-router-dom'

// "podium." with the tomato dot. Renders a link when given `to`.
export default function Wordmark({ to, style, onClick }) {
  const inner = <>podium<span>.</span></>
  return to
    ? <Link className="wordmark" to={to} style={style} onClick={onClick}>{inner}</Link>
    : <span className="wordmark" style={style}>{inner}</span>
}
