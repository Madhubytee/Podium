import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { clock } from '../../lib/format'

// One series, so no legend: the heading names it. The olive band is the 130 to 160 wpm target.
const INK_MUTE = '#8A725F'
const RULE = '#E2D2BD'
const TOMATO = '#C4513A'
const OLIVE = '#5F6E33'

function Tip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return <div className="chart-tip"><b>{Math.round(p.wpm)} wpm</b> at {clock(p.t)}</div>
}

export default function PaceChart({ data }) {
  const max = Math.max(200, ...data.map((d) => d.wpm)) + 10
  return (
    <div className="chart" role="img" aria-label={`Pace over the take, from ${Math.round(data[0].wpm)} to ${Math.round(data.at(-1).wpm)} words per minute`}>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke={RULE} />
          <ReferenceArea y1={130} y2={160} fill={OLIVE} fillOpacity={0.1} stroke="none" ifOverflow="extendDomain" />
          <XAxis dataKey="t" type="number" domain={['dataMin', 'dataMax']} tickFormatter={clock}
                 tick={{ fill: INK_MUTE, fontSize: 12 }} axisLine={{ stroke: RULE }} tickLine={false} />
          <YAxis domain={[60, Math.ceil(max / 20) * 20]} tick={{ fill: INK_MUTE, fontSize: 12 }}
                 axisLine={false} tickLine={false} width={44} />
          <Tooltip content={<Tip />} cursor={{ stroke: INK_MUTE, strokeWidth: 1 }} />
          <Line type="monotone" dataKey="wpm" stroke={TOMATO} strokeWidth={2} isAnimationActive={false}
                dot={{ r: 4, fill: TOMATO, stroke: '#FAF3E8', strokeWidth: 2 }}
                activeDot={{ r: 5, fill: TOMATO, stroke: '#FAF3E8', strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
