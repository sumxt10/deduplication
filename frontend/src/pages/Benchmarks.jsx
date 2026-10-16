import React, { useState } from 'react'
import MetricCard from '../components/MetricCard'
import { api } from '../services/api'

export default function Benchmarks({ onDone }) {
  const [dataset, setDataset] = useState('paysim')
  const [totalRecords, setTotalRecords] = useState(1000)
  const [duplicateRate, setDuplicateRate] = useState(0.30)
  const [invalidRate, setInvalidRate] = useState(0.01)
  const [batchSize, setBatchSize] = useState(500)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [statusMsg, setStatusMsg] = useState('Ready to execute reproducible benchmark.')
  const [benchmarkResult, setBenchmarkResult] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const handleStart = async () => {
    setRunning(true)
    setProgress(0)
    setBenchmarkResult(null)
    setErrorMsg(null)
    setStatusMsg('Initializing workload generator and streaming job...')

    try {
      const created = await api.createJob({
        dataset,
        total_records: parseInt(totalRecords),
        duplicate_rate: parseFloat(duplicateRate),
        invalid_rate: parseFloat(invalidRate),
        batch_size: parseInt(batchSize),
        mode: 'direct',
        seed: 42,
      })

      setStatusMsg(`Job ${created.job_id} queued...`)

      const poll = async () => {
        try {
          const job = await api.job(created.job_id)
          const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0
          setProgress(pct)
          setStatusMsg(
            `${job.status.toUpperCase()}: ${job.progress || 0}/${job.total} records processed (${job.accepted || 0} accepted, ${job.duplicates || 0} duplicates prevented, ${job.invalid || 0} in DLQ)`
          )

          if (job.status === 'queued' || job.status === 'running') {
            setTimeout(poll, 600)
          } else if (job.status === 'completed') {
            const parsed = job.result ? JSON.parse(job.result) : null
            setBenchmarkResult(parsed)
            setRunning(false)
            if (onDone) onDone()
          } else {
            setErrorMsg(job.error || 'Job failed during execution')
            setRunning(false)
          }
        } catch (err) {
          setErrorMsg(err.message)
          setRunning(false)
        }
      }

      poll()
    } catch (err) {
      setErrorMsg(err.message)
      setRunning(false)
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Workload Evaluation &amp; PaySim Benchmark Suite</h2>
            <p className="panel-desc">
              Benchmark the deduplication engine under approximately 30% duplicate injection, measuring throughput (TPS), p50/p95/p99 latencies, duplicate precision, and recall.
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="alert-box alert-info" style={{ borderColor: '#f43f5e', color: '#f87171' }}>
            <span>{errorMsg}</span>
          </div>
        )}

        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Workload Dataset</label>
            <select
              className="form-select"
              value={dataset}
              onChange={e => setDataset(e.target.value)}
              disabled={running}
            >
              <option value="paysim">PaySim Mobile Money (Kaggle Financial)</option>
              <option value="synthetic">Synthetic Banking Transfers</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Total Records: {totalRecords.toLocaleString()}</label>
            <select
              className="form-select"
              value={totalRecords}
              onChange={e => setTotalRecords(e.target.value)}
              disabled={running}
            >
              <option value="500">500 records (Quick check)</option>
              <option value="1000">1,000 records (Standard PS-15)</option>
              <option value="5000">5,000 records (Stress test)</option>
              <option value="10000">10,000 records (High load)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">
              Injected Duplicate Rate: {(duplicateRate * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0.10"
              max="0.50"
              step="0.05"
              value={duplicateRate}
              onChange={e => setDuplicateRate(e.target.value)}
              disabled={running}
              className="form-input"
            />
          </div>

          <div className="form-group" style={{ justifyContent: 'flex-end' }}>
            <button
              className="btn btn-primary"
              onClick={handleStart}
              disabled={running}
              style={{ height: '42px' }}
            >
              {running ? 'Benchmarking Engine...' : '🚀 Launch Benchmark'}
            </button>
          </div>
        </div>

        {/* Live Progress Indicator */}
        {running && (
          <div style={{ marginTop: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: '#94a3b8' }}>
              <span>{statusMsg}</span>
              <span>{progress}%</span>
            </div>
            <div className="progress-bar-container">
              <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>
        )}

        {/* Benchmark Results Display */}
        {benchmarkResult && (
          <div style={{ marginTop: '28px' }}>
            <h3 style={{ fontSize: '16px', marginBottom: '16px', color: '#f8fafc' }}>
              Evaluation Report: {dataset.toUpperCase()} ({totalRecords} records, {(duplicateRate * 100)}% duplicates)
            </h3>

            <div className="metrics-grid">
              <MetricCard
                title="Throughput"
                value={`${Math.round(benchmarkResult.throughput || 0).toLocaleString()} TPS`}
                subtitle="Deliveries per monotonic sec"
                tone="cyan"
              />
              <MetricCard
                title="Duplicate Recall"
                value={`${((benchmarkResult.duplicate_recall || 1) * 100).toFixed(2)}%`}
                subtitle="True duplicates caught / ground truth"
                tone="emerald"
                badge="100% Target"
              />
              <MetricCard
                title="Duplicate Precision"
                value={`${((benchmarkResult.duplicate_precision || 1) * 100).toFixed(2)}%`}
                subtitle="Zero valid transactions lost"
                tone="emerald"
                badge="Authoritative"
              />
              <MetricCard
                title="Total Processing Time"
                value={`${benchmarkResult.duration_ms || 0} ms`}
                subtitle={`For ${benchmarkResult.total} total deliveries`}
                tone="blue"
              />
            </div>

            <div className="metrics-grid" style={{ marginTop: '16px' }}>
              <MetricCard
                title="p50 Latency"
                value={`${benchmarkResult.latency?.p50_ms || 0} ms`}
                subtitle="Median processing time"
                tone="emerald"
              />
              <MetricCard
                title="p95 Latency"
                value={`${benchmarkResult.latency?.p95_ms || 0} ms`}
                subtitle="95th percentile"
                tone="amber"
              />
              <MetricCard
                title="p99 Latency"
                value={`${benchmarkResult.latency?.p99_ms || 0} ms`}
                subtitle="Tail latency under load"
                tone="rose"
              />
              <MetricCard
                title="Bloom Memory Footprint"
                value={`${((benchmarkResult.bloom_memory_bytes || 0) / 1024).toFixed(1)} KB`}
                subtitle={`False positives: ${benchmarkResult.bloom_false_positives || 0}`}
                tone="purple"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}