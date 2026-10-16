import React from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

export default function LatencyChart({ latencyHistory = [] }) {
  const data = latencyHistory.length > 0
    ? latencyHistory
    : [
        { name: 'T-4', p50: 0.12, p95: 0.35, p99: 0.65 },
        { name: 'T-3', p50: 0.14, p95: 0.38, p99: 0.72 },
        { name: 'T-2', p50: 0.13, p95: 0.32, p99: 0.60 },
        { name: 'T-1', p50: 0.15, p95: 0.40, p99: 0.81 },
        { name: 'Now', p50: 0.14, p95: 0.36, p99: 0.68 },
      ]

  return (
    <div style={{ width: '100%', height: 260 }}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="p50Grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="p95Grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="p99Grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f293d" />
          <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
          <YAxis stroke="#64748b" fontSize={11} unit="ms" />
          <Tooltip
            contentStyle={{
              backgroundColor: '#111827',
              borderColor: '#1f293d',
              borderRadius: '8px',
              fontSize: '12px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }} />
          <Area
            type="monotone"
            dataKey="p50"
            name="p50 Latency (ms)"
            stroke="#10b981"
            fillOpacity={1}
            fill="url(#p50Grad)"
          />
          <Area
            type="monotone"
            dataKey="p95"
            name="p95 Latency (ms)"
            stroke="#f59e0b"
            fillOpacity={1}
            fill="url(#p95Grad)"
          />
          <Area
            type="monotone"
            dataKey="p99"
            name="p99 Latency (ms)"
            stroke="#f43f5e"
            fillOpacity={1}
            fill="url(#p99Grad)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
