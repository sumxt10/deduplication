import React, { useState } from 'react'
import EventsTable from '../components/EventsTable'
import { api } from '../services/api'

export default function Transactions({ events = [], onRefresh, onReplay, loading }) {
  const [form, setForm] = useState({
    event_id: `evt-${Date.now().toString().slice(-6)}`,
    transaction_id: `tx-${Date.now().toString().slice(-6)}`,
    sender_account: 'ACC-01001',
    receiver_account: 'ACC-02002',
    amount: '2500.00',
    currency: 'INR',
  })
  const [submitting, setSubmitting] = useState(false)
  const [resultMsg, setResultMsg] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')

  const handleGenerateRandom = () => {
    const id = Date.now().toString().slice(-6)
    setForm({
      event_id: `evt-${id}`,
      transaction_id: `tx-${id}`,
      sender_account: `ACC-${Math.floor(1000 + Math.random() * 8999)}`,
      receiver_account: `ACC-${Math.floor(10000 + Math.random() * 89999)}`,
      amount: (Math.random() * 10000 + 10).toFixed(2),
      currency: 'INR',
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setResultMsg(null)
    try {
      const payload = {
        ...form,
        amount: parseFloat(form.amount),
        timestamp: new Date().toISOString(),
        transaction_type: 'transfer',
        schema_version: 1,
        source: 'dashboard_studio',
      }
      const res = await api.ingest(payload)
      setResultMsg({
        type: res.status === 'accepted' ? 'success' : 'info',
        text: `${res.status.toUpperCase()}: ${res.reason || 'Committed atomically to ledger'}. Latency: ${res.latency_us ? `${res.latency_us} μs` : 'N/A'}`,
      })
      handleGenerateRandom()
      onRefresh()
    } catch (err) {
      setResultMsg({ type: 'danger', text: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const handleTriggerBurst = async () => {
    setSubmitting(true)
    setResultMsg(null)
    try {
      // Create 10 events with exactly 3 duplicates (30% duplicate rate)
      const baseEvents = []
      for (let i = 0; i < 7; i++) {
        const id = `${Date.now()}-${i}`
        baseEvents.push({
          event_id: `burst-evt-${id}`,
          transaction_id: `burst-tx-${id}`,
          sender_account: `ACC-BURST-${i}`,
          receiver_account: `ACC-DEST-${i}`,
          amount: (500 + i * 150).toFixed(2),
          currency: 'INR',
          timestamp: new Date().toISOString(),
          transaction_type: 'transfer',
          schema_version: 1,
          source: 'burst_generator',
        })
      }
      // Inject 3 duplicates of the first 3 events
      const duplicates = [baseEvents[0], baseEvents[1], baseEvents[2]].map(item => ({ ...item }))
      const allEvents = [...baseEvents, ...duplicates]

      const res = await api.ingestBatch(allEvents)
      const results = res.results || []
      const accepted = results.filter(r => r.status === 'accepted').length
      const dups = results.filter(r => r.status === 'duplicate').length

      setResultMsg({
        type: 'success',
        text: `Burst completed: ${allEvents.length} events injected (30% duplicate rate). Accepted: ${accepted}, Duplicates Detected: ${dups}`,
      })
      onRefresh()
    } catch (err) {
      setResultMsg({ type: 'danger', text: err.message })
    } finally {
      setSubmitting(false)
    }
  }

  const filteredEvents = statusFilter
    ? events.filter(e => e.status === statusFilter)
    : events

  return (
    <div>
      {/* Studio Card */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Transaction Studio &amp; Duplicate Injector</h2>
            <p className="panel-desc">
              Submit bespoke transfer events or trigger automated bursts with 30% duplicate injection to test idempotent processing.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button className="btn btn-secondary" onClick={handleGenerateRandom} type="button">
              🎲 Randomize
            </button>
            <button
              className="btn btn-primary"
              onClick={handleTriggerBurst}
              disabled={submitting}
              type="button"
            >
              ⚡ Trigger 30% Duplicate Burst
            </button>
          </div>
        </div>

        {resultMsg && (
          <div className={`alert-box alert-${resultMsg.type === 'danger' ? 'info' : resultMsg.type}`} style={resultMsg.type === 'danger' ? { borderColor: '#f43f5e', color: '#f87171' } : {}}>
            <span>{resultMsg.text}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-grid">
            <div className="form-group">
              <label className="form-label">Event ID</label>
              <input
                className="form-input"
                required
                value={form.event_id}
                onChange={e => setForm({ ...form, event_id: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Transaction ID</label>
              <input
                className="form-input"
                required
                value={form.transaction_id}
                onChange={e => setForm({ ...form, transaction_id: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Sender Account</label>
              <input
                className="form-input"
                required
                value={form.sender_account}
                onChange={e => setForm({ ...form, sender_account: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Receiver Account</label>
              <input
                className="form-input"
                required
                value={form.receiver_account}
                onChange={e => setForm({ ...form, receiver_account: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Amount (INR)</label>
              <input
                className="form-input"
                type="number"
                step="0.01"
                min="0.01"
                required
                value={form.amount}
                onChange={e => setForm({ ...form, amount: e.target.value })}
              />
            </div>
            <div className="form-group" style={{ justifyContent: 'flex-end' }}>
              <button className="btn btn-primary" type="submit" disabled={submitting} style={{ height: '42px' }}>
                {submitting ? 'Processing...' : '▶ Ingest Event'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Events Ledger with Filters */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Processed Event Ledger</h2>
            <p className="panel-desc">Authoritative audit record of accepted transfers, prevented duplicates, and conflict states.</p>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['', 'accepted', 'duplicate', 'conflict'].map(st => (
              <button
                key={st}
                className={`btn ${statusFilter === st ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 12px', fontSize: '12px' }}
                onClick={() => setStatusFilter(st)}
              >
                {st ? st.toUpperCase() : 'ALL'}
              </button>
            ))}
          </div>
        </div>

        <EventsTable
          events={filteredEvents}
          onReplay={onReplay}
          loading={loading}
        />
      </div>
    </div>
  )
}