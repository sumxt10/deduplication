import React from 'react'

export default function PipelineVisualizer({ mode = 'direct', cdcStats = {}, bloomStats = {} }) {
  return (
    <div className="pipeline-container" id="pipeline-visualizer">
      <div className="pipeline-node active">
        <div className="pipeline-node-icon">🏦</div>
        <div className="pipeline-node-title">Source Core DB</div>
        <div className="pipeline-node-sub">WAL Mutations &amp; State</div>
      </div>

      <div className="pipeline-arrow">➔</div>

      <div className="pipeline-node active">
        <div className="pipeline-node-icon">⚡</div>
        <div className="pipeline-node-title">CDC Log Tailer</div>
        <div className="pipeline-node-sub">
          {cdcStats.wal_records_generated || 0} LSNs captured
        </div>
      </div>

      <div className="pipeline-arrow">➔</div>

      <div className="pipeline-node active">
        <div className="pipeline-node-icon">📨</div>
        <div className="pipeline-node-title">Event Broker (Kafka)</div>
        <div className="pipeline-node-sub">Topic: financial-events</div>
      </div>

      <div className="pipeline-arrow">➔</div>

      <div className="pipeline-node active">
        <div className="pipeline-node-icon">🔍</div>
        <div className="pipeline-node-title">Sliding Bloom Filter</div>
        <div className="pipeline-node-sub">
          {bloomStats.memory_bytes ? `${Math.round(bloomStats.memory_bytes / 1024)} KB hint` : 'In-Memory'}
        </div>
      </div>

      <div className="pipeline-arrow">➔</div>

      <div className="pipeline-node active">
        <div className="pipeline-node-icon">🛡️</div>
        <div className="pipeline-node-title">Authoritative State</div>
        <div className="pipeline-node-sub">Atomic SQL Unique Index</div>
      </div>

      <div className="pipeline-arrow">➔</div>

      <div className="pipeline-node">
        <div className="pipeline-node-icon">⚖️</div>
        <div className="pipeline-node-title">Ledger &amp; Accounts</div>
        <div className="pipeline-node-sub">Balanced Double-Entry</div>
      </div>
    </div>
  )
}
