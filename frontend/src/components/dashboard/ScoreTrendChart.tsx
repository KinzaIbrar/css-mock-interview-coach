import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TrendPoint } from '@/api/types'
import { formatDate } from '@/utils/format'

/** Real scores only: one point per completed interview, straight from /dashboard `score_trend`. */
export default function ScoreTrendChart({ points }: { points: TrendPoint[] }) {
  const data = points.map((p, i) => ({ n: i + 1, score: p.score, subject: p.subject, date: formatDate(p.completed_at) }))
  return (
    <div>
      <div className="h-56 w-full" role="img" aria-label={`Score trend across your last ${points.length} completed interview${points.length === 1 ? '' : 's'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="n" tickLine={false} axisLine={false} tick={{ fill: '#5b6b82', fontSize: 12 }} allowDecimals={false} label={{ value: 'Interview', position: 'insideBottom', offset: -2, fill: '#5b6b82', fontSize: 11 }} height={32} />
            <YAxis domain={[0, 100]} tickLine={false} axisLine={false} tick={{ fill: '#5b6b82', fontSize: 12 }} width={44} />
            <Tooltip
              cursor={{ stroke: '#cbd5e1' }}
              formatter={(value) => [`${Number(value).toFixed(1)} / 100`, 'Score']}
              labelFormatter={(_, payload) => {
                const p = payload?.[0]?.payload as { subject: string; date: string } | undefined
                return p ? `${p.subject} · ${p.date}` : ''
              }}
              contentStyle={{ borderRadius: 8, border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgb(11 27 58 / 0.08)', fontSize: 13 }}
            />
            <Line type="monotone" dataKey="score" stroke="#1d4ed8" strokeWidth={2.5} dot={{ r: 4, fill: '#1d4ed8', strokeWidth: 0 }} activeDot={{ r: 6 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Score trend data</caption>
        <thead><tr><th>Interview</th><th>Subject</th><th>Date</th><th>Score</th></tr></thead>
        <tbody>{data.map((d) => <tr key={d.n}><td>{d.n}</td><td>{d.subject}</td><td>{d.date}</td><td>{d.score}</td></tr>)}</tbody>
      </table>
    </div>
  )
}
