import React from 'react'

export default function MetricCard({ title, value, subtitle, tone, icon: Icon, badge }) {
  const getToneColor = () => {
    switch (tone) {
      case 'emerald':
        return '#10b981'
      case 'amber':
        return '#f59e0b'
      case 'rose':
        return '#f43f5e'
      case 'cyan':
        return '#06b6d4'
      case 'purple':
        return '#8b5cf6'
      default:
        return '#3b82f6'
    }
  }

  return (
    <div className="metric-card" id={`metric-card-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="metric-card-header">
        <span className="metric-card-title">{title}</span>
        {badge && <span className="badge badge-resolved">{badge}</span>}
      </div>
      <div className="metric-card-value" style={{ color: tone ? getToneColor() : undefined }}>
        {value}
      </div>
      {subtitle && <div className="metric-card-subtitle">{subtitle}</div>}
    </div>
  )
}