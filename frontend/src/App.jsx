import { useEffect, useState } from 'react'
import { api } from './services/api'

function Card({ label, value, tone = '' }) { return <div className="card"><small>{label}</small><strong className={tone}>{value}</strong></div> }
function App() {
  const [summary, setSummary] = useState(null); const [events, setEvents] = useState([]); const [error, setError] = useState('')
  const [page, setPage] = useState('Overview')
  const load = async () => { try { setSummary(await api.summary()); setEvents((await api.events()).items) } catch (e) { setError(e.message) } }
  useEffect(() => { load(); const timer = setInterval(load, 5000); return () => clearInterval(timer) }, [])
  const s = summary?.summary || {}
  return <div className="app"><aside><h1>PS-15</h1><p>Exactly-once engine</p>{['Overview', 'Transactions', 'Dead Letter Queue', 'Benchmarks', 'Settings'].map(item => <button className={page === item ? 'nav active' : 'nav'} onClick={() => setPage(item)} key={item}>{item}</button>)}</aside>
    <main><header><div><span className="eyebrow">OPERATIONS CONSOLE</span><h2>{page}</h2></div><span className="status">● {summary ? 'Database ready' : 'Connecting'}</span></header>
      {error && <div className="error">{error}</div>}
      {page === 'Overview' && <><section className="grid"><Card label="Total deliveries" value={s.total_deliveries || 0}/><Card label="Committed transactions" value={s.accepted || 0} tone="good"/><Card label="Duplicates prevented" value={s.duplicates || 0} tone="warn"/><Card label="Dead-letter events" value={s.invalid || 0} tone="bad"/></section><section className="panel"><h3>Recent processing activity</h3><Events rows={events}/></section></>}
      {page === 'Transactions' && <Transactions onDone={load} rows={events}/>}
      {page === 'Dead Letter Queue' && <DLQ/>}
      {page === 'Benchmarks' && <Benchmark onDone={load}/>}
      {page === 'Settings' && <Settings summary={summary} onReset={async () => { if (confirm('Reset all demo data?')) { await api.reset(); load() } }}/>}
    </main></div>
}
function Events({ rows }) { return rows.length ? <table><thead><tr><th>Event</th><th>Transaction</th><th>Status</th><th>Reason</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td>{row.event_id}</td><td>{row.transaction_id}</td><td><span className={`badge ${row.status}`}>{row.status}</span></td><td>{row.reason || 'Committed atomically'}</td></tr>)}</tbody></table> : <div className="empty">No events have been processed yet.</div> }
function DLQ() { const [data, setData] = useState(null); const [error, setError] = useState(''); useEffect(() => { api.dlq().then(setData).catch(e => setError(e.message)) }, []); return <section className="panel"><h3>Dead-letter queue</h3>{error ? <div className="error">{error}</div> : <Events rows={(data?.items || []).map(row => ({ ...row, transaction_id: '-', status: 'invalid' }))}/>}</section> }
function Transactions({ rows, onDone }) {
  const [form, setForm] = useState({ event_id: '', transaction_id: '', sender_account: 'ACC-10001', receiver_account: 'ACC-10002', amount: '5000.00' })
  const [message, setMessage] = useState('')
  const submit = async (event) => {
    event.preventDefault()
    try {
      const result = await api.ingest({ ...form, timestamp: new Date().toISOString(), currency: 'INR', transaction_type: 'transfer', schema_version: 1, source: 'dashboard' })
      setMessage(`${result.status}: ${result.reason || 'financial effect committed atomically'}`); onDone()
    } catch (e) { setMessage(e.message) }
  }
  return <><section className="panel"><h3>Submit a transaction event</h3><form className="event-form" onSubmit={submit}>{['event_id', 'transaction_id', 'sender_account', 'receiver_account', 'amount'].map(name => <label key={name}>{name.replace('_', ' ')}<input required value={form[name]} onChange={e => setForm({ ...form, [name]: e.target.value })}/></label>)}<button className="primary" type="submit">Process event</button></form>{message && <p className="result">{message}</p>}</section><section className="panel"><h3>Processed event ledger</h3><Events rows={rows}/></section></>
}
function Benchmark({ onDone }) {
  const [message, setMessage] = useState('Run a reproducible 1,000-record benchmark in direct mode.')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const start = async () => {
    setRunning(true)
    try {
      const created = await api.createJob({ total_records: 1000, duplicate_rate: 0.3, invalid_rate: 0.01, seed: 42, batch_size: 100, mode: 'direct' })
      setMessage(`Job ${created.job_id} queued...`)
      const poll = async () => {
        const job = await api.job(created.job_id)
        setMessage(`${job.status}: ${job.progress || 0}/${job.total} processed, ${job.accepted || 0} accepted, ${job.duplicates || 0} duplicates, ${job.invalid || 0} invalid`)
        if (job.status === 'queued' || job.status === 'running') return setTimeout(poll, 1000)
        setResult(job.result ? JSON.parse(job.result) : null)
        setRunning(false); onDone()
      }
      poll()
    } catch (e) { setMessage(e.message); setRunning(false) }
  }
  return <section className="panel"><h3>Benchmark</h3><p>{message}</p><button className="primary" disabled={running} onClick={start}>{running ? 'Running...' : 'Start quick benchmark'}</button>{result && <div className="benchmark-result"><Card label="Throughput" value={`${Math.round(result.throughput)} events/s`} /><Card label="Duplicate precision" value={`${(result.duplicate_precision * 100).toFixed(1)}%`} tone="good" /><Card label="Duplicate recall" value={`${(result.duplicate_recall * 100).toFixed(1)}%`} tone="good" /><Card label="Duration" value={`${result.duration_ms.toFixed(0)} ms`} /></div>}</section>
}
function Settings({ summary, onReset }) { return <section className="panel"><h3>System configuration</h3><p>Mode: <b>{summary?.mode || 'direct'}</b></p><p>Bloom memory: {summary?.bloom?.memory_bytes || 0} bytes</p><button className="danger" onClick={onReset}>Reset demo data</button></section> }
export default App