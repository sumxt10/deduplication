import React from 'react'

export default function EventsTable({ events = [], onReplay, loading = false }) {
  if (!events || events.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '36px', color: '#64748b', fontSize: '14px' }}>
        No events have been processed yet. Submit a transaction or trigger a CDC simulation to see live activity.
      </div>
    )
  }

  const getBadgeClass = (status) => {
    switch (status) {
      case 'accepted':
        return 'badge-accepted'
      case 'duplicate':
        return 'badge-duplicate'
      case 'conflict':
        return 'badge-conflict'
      default:
        return 'badge-invalid'
    }
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Event ID</th>
            <th>Transaction ID</th>
            <th>Status</th>
            <th>Reason / Details</th>
            <th>Timestamp</th>
            <th style={{ textAlign: 'right' }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {events.map((ev, index) => {
            const isJsonPayload = ev.payload && typeof ev.payload === 'string'
            let parsed = null
            if (isJsonPayload) {
              try {
                parsed = JSON.parse(ev.payload)
              } catch (_) {}
            }

            return (
              <tr key={ev.id || `${ev.event_id}-${index}`}>
                <td style={{ fontFamily: 'monospace', color: '#93c5fd' }}>
                  {ev.event_id || parsed?.event_id || 'N/A'}
                </td>
                <td style={{ fontFamily: 'monospace' }}>
                  {ev.transaction_id || parsed?.transaction_id || '—'}
                </td>
                <td>
                  <span className={`badge ${getBadgeClass(ev.status)}`}>
                    {ev.status || 'unknown'}
                  </span>
                </td>
                <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ev.reason || 'Committed atomically to ledger'}
                </td>
                <td style={{ fontSize: '11px', color: '#64748b' }}>
                  {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : 'Just now'}
                </td>
                <td style={{ textAlign: 'right' }}>
                  {onReplay && ev.event_id && (
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 10px', fontSize: '11px' }}
                      onClick={() => onReplay(ev.event_id)}
                      disabled={loading}
                      title="Send this event again to verify duplicate detection"
                    >
                      🔁 Replay
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}