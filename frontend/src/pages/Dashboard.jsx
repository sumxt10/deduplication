import React from 'react'
import MetricCard from '../components/MetricCard'
import PipelineVisualizer from '../components/PipelineVisualizer'
import LatencyChart from '../components/LatencyChart'
import EventsTable from '../components/EventsTable'

export default function Dashboard({ summary, latency, cdc, events, onReplay, loading, latencyHistory }) {
  const s = summary?.summary || {}
  const bloom = summary?.bloom || {}
  const lat = latency?.total_latency || summary?.latency?.total_latency || {}

  const duplicateRatePercent = s.total_deliveries > 0
    ? ((s.duplicates / s.total_deliveries) * 100).toFixed(1)
    : '0.0'

  return (
    <div>
      {/* KPI Cards Row */}
      <div className="metrics-grid">
        <MetricCard
          title="Total Events Ingested"
          value={s.total_deliveries || 0}
          subtitle="Processed through CDC & API"
          tone="blue"
        />
        <MetricCard
          title="Committed Transactions"
          value={s.accepted || 0}
          subtitle="Atomic double-entry ledger"
          tone="emerald"
          badge="Exactly Once"
        />
        <MetricCard
          title="Duplicates Prevented"
          value={s.duplicates || 0}
          subtitle={`${duplicateRatePercent}% of deliveries screened`}
          tone="amber"
          badge="100% Recall"
        />
        <MetricCard
          title="Dead Letter Queue"
          value={s.unresolved_dlq ?? s.invalid ?? 0}
          subtitle="Isolated malformed events"
          tone="rose"
        />
        <MetricCard
          title="p95 Latency"
          value={`${lat.p95_ms || 0} ms`}
          subtitle={`p50: ${lat.p50_ms || 0} ms | p99: ${lat.p99_ms || 0} ms`}
          tone="cyan"
        />
        <MetricCard
          title="Bloom Filter Memory"
          value={bloom.memory_bytes ? `${(bloom.memory_bytes / 1024).toFixed(1)} KB` : '0 KB'}
          subtitle={`${bloom.slices || 3} rotating windows | 0 FP`}
          tone="purple"
        />
      </div>

      {/* CDC Pipeline Visual Flow */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">End-to-End Pipeline Architecture</h2>
            <p className="panel-desc">Real-time status across CDC ingestion, message broker, Bloom screening hint, and authoritative SQL persistence.</p>
          </div>
        </div>
        <PipelineVisualizer
          mode={summary?.mode}
          cdcStats={cdc}
          bloomStats={bloom}
        />
      </div>

      {/* Latency Distribution */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Real-Time Processing Latency Percentiles</h2>
            <p className="panel-desc">Microsecond-level performance across canonical hashing, Bloom screening, and atomic SQLite commits.</p>
          </div>
        </div>
        <LatencyChart latencyHistory={latencyHistory} />
      </div>

      {/* Recent Processing Feed */}
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Recent Ingestion Activity</h2>
            <p className="panel-desc">Showing latest transactional events and automated duplicate classifications.</p>
          </div>
        </div>
        <EventsTable events={events} onReplay={onReplay} loading={loading} />
      </div>
    </div>
  )
}