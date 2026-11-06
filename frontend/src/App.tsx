import { useEffect, useState } from 'react'
import axios from 'axios'

export default function App() {
  const [status, setStatus] = useState('checking…')
  useEffect(() => {
    axios.get('/api/health').then((r) => setStatus(`${r.data.status} (${r.data.ai_mode})`)).catch(() => setStatus('backend unreachable'))
  }, [])
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center">
      <div className="rounded-xl bg-white p-8 shadow-sm border border-slate-200">
        <h1 className="text-xl font-semibold">CSS Mock Interview Coach</h1>
        <p className="mt-2 text-sm text-slate-600">Backend: {status}</p>
      </div>
    </main>
  )
}
