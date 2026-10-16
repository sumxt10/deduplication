import React, { useEffect, useState } from 'react'
import { api } from '../services/api'

export default function DeadLetterQueue({ onRefreshParent }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [actionMsg, setActionMsg] = useState(null)
  const [filterStatus, setFilterStatus] = useState('unresolved')

  const fetchDLQ = async () => {
    setLoading(true)
    try {
      const query = filterStatus ? `?status=${filterStatus}&page_size=100` : '?page_size=100'
      const res = await api.dlq(query)
      setItems(res.items || [])
      setTotal(res.total || 0)
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDLQ()
  }, [filterStatus])

  const handleRedrive = async (id) => {
    setLoading(true)
    try {
      const res = await api.redriveDlq(id)
      if (res.success) {
        setActionMsg({
          type: 'success',
          text: `Event #${id} successfully redriven! Result: ${res.result?.status || 'Accepted'}`,
        })
        fetchDLQ()
        if (onRefreshParent) onRefreshParent()
      } else {
        setActionMsg({ type: 'danger', text: `Redrive failed: ${res.error}` })
      }
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleRedriveAll = async () => {
    setLoading(true)
    try {
      const res = await api.redriveAllDlq()
      setActionMsg({
        type: 'success',
        text: `Batch redrive executed: ${res.redriven_count} items processed.`,
      })
      fetchDLQ()
      if (onRefreshParent) onRefreshParent()
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm(`Discard and permanently remove DLQ event #${id}?`)) return
    setLoading(true)
    try {
      await api.deleteDlq(id)
      setActionMsg({ type: 'info', text: `Event #${id} discarded from DLQ.` })
      fetchDLQ()
      if (onRefreshParent) onRefreshParent()
    } catch (err) {
      setActionMsg({ type: 'danger', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Dead Letter Queue (DLQ) Inspector &amp; Recovery</h2>
            <p className="panel-desc">
              Events rejected due to schema violations, malformed payloads, or business rule errors are quarantined here without impacting valid transfers.
            </p>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <div style={{ display: 'flex', gap: '6px' }}>
              {['unresolved', 'resolved', ''].map(st => (
                <button
                  key={st}
                  className={`btn ${filterStatus === st ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '6px 12px', fontSize: '12px' }}
                  onClick={() => setFilterStatus(st)}
                >
                  {st ? st.toUpperCase() : 'ALL'}
                </button>
              ))}
            </div>
            <button
              className="btn btn-primary"
              onClick={handleRedriveAll}
              disabled={loading || items.length === 0}
            >
              🚀 Redrive All Unresolved
            </button>
          </div>
        </div>

        {actionMsg && (
          <div
            className={`alert-box alert-${actionMsg.type === 'danger' ? 'info' : actionMsg.type}`}
            style={actionMsg.type === 'danger' ? { borderColor: '#f43f5e', color: '#f87171' } : {}}
          >
            <span>{actionMsg.text}</span>
          </div>
        )}

        {items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px', color: '#64748b' }}>
            🎉 No {filterStatus || ''} dead-letter events found. The processing pipeline is healthy!
          </div>
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Event ID</th>
                  <th>Rejection Reason</th>
                  <th>Status</th>
                  <th>Captured At</th>
                  <th style={{ textAlign: 'right' }}>Recovery Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td>#{item.id}</td>
                    <td style={{ fontFamily: 'monospace', color: '#f87171' }}>
                      {item.event_id || 'unidentified'}
                    </td>
                    <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.reason}>
                      {item.reason}
                    </td>
                    <td>
                      <span className={`badge ${item.status === 'resolved' ? 'badge-resolved' : 'badge-invalid'}`}>
                        {item.status}
                      </span>
                    </td>
                    <td style={{ fontSize: '11px', color: '#64748b' }}>
                      {new Date(item.created_at).toLocaleTimeString()}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        {item.status !== 'resolved' && (
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 10px', fontSize: '11px' }}
                            onClick={() => handleRedrive(item.id)}
                            disabled={loading}
                          >
                            🔄 Redrive
                          </button>
                        )}
                        <button
                          className="btn btn-danger"
                          style={{ padding: '4px 10px', fontSize: '11px' }}
                          onClick={() => handleDelete(item.id)}
                          disabled={loading}
                        >
                          ✕ Discard
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}