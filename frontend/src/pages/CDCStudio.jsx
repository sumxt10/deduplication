import React, { useState } from 'react'
import { api } from '../services/api'

export default function CDCStudio({ onRefreshParent }) {
  const [totalEvents, setTotalEvents] = useState(50)
  const [duplicateRate, setDuplicateRate] = useState(0.30)
  const [burstRetry, setBurstRetry] = useState(true)
  const [running, setRunning] = useState(false)
  const [streamResult, setStreamResult] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const handleSimulate = async () => {
    setRunning(true)
    setErrorMsg(null)
    try {
      const res = await api.simulateCdc({
        total_events: parseInt(totalEvents),
        duplicate_rate: parseFloat(duplicateRate),
        network_retry_burst: burstRetry,
        interval_ms: 5,
      })
      setStreamResult(res)
      if (onRefreshParent) onRefreshParent()
    } catch (err) {
      setErrorMsg(err.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">CDC (Change Data Capture) &amp; WAL Streaming Simulator</h2>
            <p className="panel-desc">
              Emulates a production PostgreSQL/MySQL CDC connector tailing database WAL transaction logs and streaming them through message brokers with network retry bursts.
            </p>
          </div>
        </div>

        <div className="alert-box alert-info" style={{ marginBottom: '20px' }}>
          <div>
            <strong>Architecture Note (Simulated CDC vs. Enterprise Production CDC):</strong>
            <ul style={{ margin: '6px 0 0 18px', fontSize: '12px', lineHeight: 1.6 }}>
              <li><strong>Current Implementation (Simulated CDC):</strong> High-fidelity in-memory Debezium-compatible envelope generator simulating sequential LSNs, database txIDs, and at-least-once network retry bursts. Operates locally with ₹0 cloud overhead and zero external infrastructure dependencies.</li>
              <li><strong>Enterprise Production CDC:</strong> In a production AWS environment, CDC is achieved by configuring PostgreSQL with <code>wal_level = logical</code>, running a Debezium connector on Kafka Connect, and reading physical WAL segment changes to publish into Apache Kafka topics.</li>
            </ul>
          </div>
        </div>

        {errorMsg && (
          <div className="alert-box alert-info" style={{ borderColor: '#f43f5e', color: '#f87171' }}>
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Total Events to Stream: {totalEvents}</label>
            <input
              type="range"
              min="10"
              max="500"
              step="10"
              value={totalEvents}
              onChange={e => setTotalEvents(e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label className="form-label">
              Injected Duplicate Rate: {(duplicateRate * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0.0"
              max="0.60"
              step="0.05"
              value={duplicateRate}
              onChange={e => setDuplicateRate(e.target.value)}
              className="form-input"
            />
          </div>

          <div className="form-group" style={{ justifyContent: 'center' }}>
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={burstRetry}
                onChange={e => setBurstRetry(e.target.checked)}
                style={{ width: '18px', height: '18px' }}
              />
              Simulate Network Broker Retry Bursts
            </label>
          </div>

          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <button
              className="btn btn-primary"
              onClick={handleSimulate}
              disabled={running}
              style={{ height: '42px' }}
            >
              {running ? 'Streaming CDC Changes...' : '⚡ Stream CDC Events'}
            </button>
          </div>
        </div>

        {streamResult && (
          <div style={{ marginTop: '24px' }}>
            <div className="metrics-grid">
              <div className="metric-card">
                <div className="metric-card-title">Total Streamed</div>
                <div className="metric-card-value">{streamResult.total_streamed}</div>
                <div className="metric-card-subtitle">CDC envelopes emitted</div>
              </div>
              <div className="metric-card">
                <div className="metric-card-title">Unique WAL Inserts</div>
                <div className="metric-card-value" style={{ color: '#10b981' }}>
                  {streamResult.unique_original_wal}
                </div>
                <div className="metric-card-subtitle">Committed to ledger</div>
              </div>
              <div className="metric-card">
                <div className="metric-card-title">Duplicates Injected</div>
                <div className="metric-card-value" style={{ color: '#f59e0b' }}>
                  {streamResult.duplicates_injected}
                </div>
                <div className="metric-card-subtitle">Simulated broker retries</div>
              </div>
              <div className="metric-card">
                <div className="metric-card-title">Deduplication Accuracy</div>
                <div className="metric-card-value" style={{ color: '#3b82f6' }}>
                  {streamResult.duplicate_detection_accuracy}%
                </div>
                <div className="metric-card-subtitle">Zero double-spending</div>
              </div>
            </div>

            <h3 style={{ fontSize: '15px', margin: '20px 0 12px', color: '#94a3b8' }}>
              Streamed CDC Records Log (Latest 50)
            </h3>
            <div className="table-responsive">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Log Sequence No. (LSN)</th>
                    <th>Database TxID</th>
                    <th>Event ID</th>
                    <th>Delivery Attempt</th>
                    <th>Classification</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(streamResult.results || []).slice(0, 50).map((r, idx) => (
                    <tr key={idx}>
                      <td style={{ fontFamily: 'monospace', color: '#06b6d4' }}>
                        0/{r.lsn.toString(16).toUpperCase()}
                      </td>
                      <td style={{ fontFamily: 'monospace' }}>#{r.tx_id}</td>
                      <td style={{ fontFamily: 'monospace' }}>{r.event_id}</td>
                      <td>
                        {r.is_retry ? (
                          <span className="badge badge-duplicate">Retry #{r.delivery_attempt}</span>
                        ) : (
                          <span className="badge badge-resolved">Original #1</span>
                        )}
                      </td>
                      <td>{r.is_retry ? 'Simulated Duplicate' : 'Unique Transaction'}</td>
                      <td>
                        <span className={`badge ${r.status === 'accepted' ? 'badge-accepted' : 'badge-duplicate'}`}>
                          {r.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
