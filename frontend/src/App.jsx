import React, { useEffect, useState, useCallback } from 'react'
import Dashboard from './pages/Dashboard'
import CDCStudio from './pages/CDCStudio'
import Transactions from './pages/Transactions'
import DeadLetterQueue from './pages/DeadLetterQueue'
import Benchmarks from './pages/Benchmarks'
import CloudArchitecture from './pages/CloudArchitecture'
import { api } from './services/api'

export default function App() {
  const [page, setPage] = useState('Dashboard')
  const [summary, setSummary] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [events, setEvents] = useState([])
  const [cdc, setCdc] = useState({})
  const [latencyHistory, setLatencyHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const loadData = useCallback(async () => {
    try {
      const [sumRes, evRes, metRes, cdcRes] = await Promise.all([
        api.summary(),
        api.events('?page_size=50'),
        api.metrics().catch(() => null),
        api.cdcStatus().catch(() => ({})),
      ])

      setSummary(sumRes)
      setEvents(evRes.items || [])
      if (metRes) {
        setMetrics(metRes)
        const lat = metRes.latency?.total_latency || sumRes?.latency?.total_latency
        if (lat) {
          const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          setLatencyHistory(prev => {
            const next = [
              ...prev,
              {
                name: nowStr,
                p50: lat.p50_ms || 0.12,
                p95: lat.p95_ms || 0.35,
                p99: lat.p99_ms || 0.65,
              },
            ]
            return next.slice(-10)
          })
        }
      }
      setCdc(cdcRes || sumRes?.cdc || {})
      setError(null)
      setLastUpdated(new Date().toLocaleTimeString())
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    loadData()
    const timer = setInterval(loadData, 4000)
    return () => clearInterval(timer)
  }, [loadData])

  const handleReplay = async (eventId) => {
    setLoading(true)
    try {
      await api.replay(eventId)
      await loadData()
    } catch (err) {
      alert(`Replay failed: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }

  const s = summary?.summary || {}
  const unresolvedDlq = s.unresolved_dlq ?? s.invalid ?? 0

  const navItems = [
    { id: 'Dashboard', label: 'Operations Dashboard', icon: '📊' },
    { id: 'CDC', label: 'CDC & WAL Streamer', icon: '⚡' },
    { id: 'Transactions', label: 'Transaction Studio', icon: '💳' },
    { id: 'DLQ', label: 'Dead Letter Queue', icon: '🛑', badge: unresolvedDlq > 0 ? unresolvedDlq : null },
    { id: 'Benchmarks', label: 'Workload Benchmarks', icon: '🚀' },
    { id: 'Architecture', label: 'AWS & Cloud Architecture', icon: '☁️' },
  ]

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className="app-sidebar">
        <div>
          <div className="brand-section">
            <div className="brand-icon">🛡️</div>
            <div>
              <div className="brand-title">PS-15 Engine</div>
              <div className="brand-subtitle">Exactly-Once Dedup</div>
            </div>
          </div>

          <nav className="nav-list">
            {navItems.map(item => (
              <button
                key={item.id}
                className={`nav-item ${page === item.id ? 'active' : ''}`}
                onClick={() => setPage(item.id)}
              >
                <span>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                {item.badge && (
                  <span className="badge badge-invalid" style={{ fontSize: '11px', padding: '2px 6px' }}>
                    {item.badge}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span>Engine Mode:</span>
            <strong style={{ color: '#60a5fa' }}>{summary?.mode?.toUpperCase() || 'DIRECT'}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Last Sync:</span>
            <span>{lastUpdated || 'Connecting...'}</span>
          </div>
        </div>
      </aside>

      {/* Main View Area */}
      <main className="app-main">
        {/* Sticky App Header */}
        <header className="app-header">
          <div className="header-left">
            <h1>{navItems.find(i => i.id === page)?.label || page}</h1>
            <p>Financial transaction stream deduplication, sliding-window Bloom filters, and atomic audit ledger</p>
          </div>
          <div className="header-right">
            <div className={`status-chip ${summary ? 'healthy' : ''}`}>
              <div className="status-dot" />
              <span>{summary ? 'Engine Online' : 'Connecting to Backend...'}</span>
            </div>
            <button
              className="btn btn-secondary"
              onClick={loadData}
              title="Refresh telemetry"
              style={{ padding: '6px 12px' }}
            >
              🔄
            </button>
          </div>
        </header>

        {/* Global Error Banner */}
        {error && (
          <div className="alert-box alert-info" style={{ margin: '16px 36px 0', borderColor: '#f43f5e', color: '#f87171' }}>
            <span>Connection Warning: {error}. Backend may be starting or offline.</span>
          </div>
        )}

        {/* Content Body */}
        <div className="content-body">
          {page === 'Dashboard' && (
            <Dashboard
              summary={summary}
              latency={metrics?.latency || summary?.latency}
              cdc={cdc}
              events={events}
              onReplay={handleReplay}
              loading={loading}
              latencyHistory={latencyHistory}
            />
          )}

          {page === 'CDC' && (
            <CDCStudio onRefreshParent={loadData} />
          )}

          {page === 'Transactions' && (
            <Transactions
              events={events}
              onRefresh={loadData}
              onReplay={handleReplay}
              loading={loading}
            />
          )}

          {page === 'DLQ' && (
            <DeadLetterQueue onRefreshParent={loadData} />
          )}

          {page === 'Benchmarks' && (
            <Benchmarks onDone={loadData} />
          )}

          {page === 'Architecture' && (
            <CloudArchitecture summary={summary} onReset={loadData} />
          )}
        </div>
      </main>
    </div>
  )
}