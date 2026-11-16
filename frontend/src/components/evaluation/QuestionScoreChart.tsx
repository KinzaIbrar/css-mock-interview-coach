import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { QuestionResult } from '@/api/types'

/** One bar per question, in order asked. A single series (the candidate's own score), so no
 * legend is needed - the section heading already says what is plotted. Skipped questions show
 * their real 0, never omitted or faked. */
export function QuestionScoreChart({ questions }: { questions: QuestionResult[] }) {
  const data = questions.map((q) => ({
    n: q.order_index + 1,
    score: q.skipped ? 0 : (q.overall ?? 0),
    topic: q.topic,
    skipped: q.skipped,
  }))
  return (
    <div>
      <div className="h-48 w-full" role="img" aria-label={`Score per question across all ${data.length} questions`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 16, right: 8, bottom: 0, left: -20 }} barCategoryGap="30%">
            <CartesianGrid stroke="#e6e4da" vertical={false} />
            <XAxis
              dataKey="n"
              tickLine={false}
              axisLine={false}
              tick={{ fill: '#75796f', fontSize: 12 }}
              tickFormatter={(n: number) => `Q${n}`}
            />
            <YAxis domain={[0, 10]} ticks={[0, 5, 10]} tickLine={false} axisLine={false} tick={{ fill: '#75796f', fontSize: 12 }} width={28} />
            <Tooltip
              cursor={{ fill: '#16281c', fillOpacity: 0.06 }}
              formatter={(value, _name, item) => [item.payload.skipped ? 'Skipped (0.0 / 10)' : `${Number(value).toFixed(1)} / 10`, 'Score']}
              labelFormatter={(n, payload) => `Question ${n}${payload?.[0]?.payload.topic ? ` · ${payload[0].payload.topic}` : ''}`}
              contentStyle={{ borderRadius: 12, border: '1px solid #e6e4da', boxShadow: '0 4px 12px rgb(20 23 26 / 0.08)', fontSize: 13 }}
            />
            <Bar dataKey="score" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.n} fill={d.skipped ? '#d7d4c6' : '#16281c'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Score per question</caption>
        <thead><tr><th>Question</th><th>Topic</th><th>Score</th></tr></thead>
        <tbody>{data.map((d) => <tr key={d.n}><td>Q{d.n}</td><td>{d.topic}</td><td>{d.skipped ? 'Skipped (0.0 / 10)' : `${d.score.toFixed(1)} / 10`}</td></tr>)}</tbody>
      </table>
    </div>
  )
}
