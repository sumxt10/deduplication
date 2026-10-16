import React, { useState, useEffect } from 'react'
import { api } from '../services/api'

export default function CloudArchitecture({ summary, onReset }) {
  const [activeTab, setActiveTab] = useState('mapping')
  const [rawMetrics, setRawMetrics] = useState('')
  const [loadingMetrics, setLoadingMetrics] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg] = useState(null)

  const fetchPrometheusMetrics = async () => {
    setLoadingMetrics(true)
    try {
      const text = await api.rawPrometheus()
      setRawMetrics(text)
    } catch (err) {
      setRawMetrics(`Failed to fetch Prometheus metrics: ${err.message}`)
    } finally {
      setLoadingMetrics(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'prometheus') {
      fetchPrometheusMetrics()
    }
  }, [activeTab])

  const handleReset = async () => {
    if (!window.confirm('Reset all demo transactions, ledger records, DLQ events, and in-memory Bloom filter?')) {
      return
    }
    setResetting(true)
    setResetMsg(null)
    try {
      await api.reset()
      setResetMsg('Database and Bloom filter successfully reset to clean state.')
      if (onReset) onReset()
    } catch (err) {
      setResetMsg(`Reset failed: ${err.message}`)
    } finally {
      setResetting(false)
    }
  }

  return (
    <div>
      {/* Top Navigation Tabs */}
      <div className="panel" style={{ padding: '16px 24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            className={`btn ${activeTab === 'mapping' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('mapping')}
          >
            ☁️ AWS Cloud Architecture Matrix
          </button>
          <button
            className={`btn ${activeTab === 'card' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('card')}
          >
            💳 Indian Debit Card (₹2 Refund Guide)
          </button>
          <button
            className={`btn ${activeTab === 'safety' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('safety')}
          >
            🛡️ Zero-Spend Safety Setup
          </button>
          <button
            className={`btn ${activeTab === 'prometheus' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('prometheus')}
          >
            📊 Live Prometheus /metrics
          </button>
          <button
            className={`btn ${activeTab === 'reset' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('reset')}
          >
            ⚙️ Engine Config &amp; Reset
          </button>
        </div>
      </div>

      {/* Tab 1: Cloud Architecture Mapping */}
      {activeTab === 'mapping' && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">AWS Production vs. Student Cost-Conscious Architecture</h2>
              <p className="panel-desc">
                Architectural blueprint comparing full-scale enterprise AWS deployment with a $0/month Free-Tier student deployment.
              </p>
            </div>
            <span className="badge badge-accepted" style={{ padding: '6px 12px' }}>
              Free Tier Optimized
            </span>
          </div>

          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Component / Tier</th>
                  <th>Enterprise AWS (Production)</th>
                  <th>Student / Free-Tier Alternative</th>
                  <th>Monthly Cost (Est.)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><strong>Compute &amp; Orchestration</strong></td>
                  <td>Amazon EKS (Managed Kubernetes)</td>
                  <td>Amazon EC2 (t3.micro / t4g.small) with k3s or Docker Compose</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (750 hrs/mo Free Tier)</td>
                </tr>
                <tr>
                  <td><strong>Messaging &amp; CDC Stream</strong></td>
                  <td>Amazon MSK (Managed Kafka)</td>
                  <td>Self-Hosted Kafka (KRaft mode) or Amazon SQS FIFO</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (1M FIFO msgs/mo)</td>
                </tr>
                <tr>
                  <td><strong>Authoritative State Store</strong></td>
                  <td>Amazon RDS PostgreSQL (Multi-AZ)</td>
                  <td>Amazon RDS db.t4g.micro (Single-AZ) or DynamoDB</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (750 hrs/mo Free Tier)</td>
                </tr>
                <tr>
                  <td><strong>Fast Bloom Screening Hint</strong></td>
                  <td>Amazon ElastiCache for Redis</td>
                  <td>In-memory rotating Bloom filter in Pod / local Redis</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (In-memory Python/C)</td>
                </tr>
                <tr>
                  <td><strong>Object Storage &amp; PaySim</strong></td>
                  <td>Amazon S3 Standard</td>
                  <td>Amazon S3 Standard</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (5 GB Free Tier)</td>
                </tr>
                <tr>
                  <td><strong>Networking</strong></td>
                  <td>VPC with Multi-AZ NAT Gateways</td>
                  <td>Single VPC with Public Subnets &amp; Security Groups</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (Avoids $32/mo NAT)</td>
                </tr>
                <tr>
                  <td><strong>Security &amp; Secrets</strong></td>
                  <td>AWS Secrets Manager + IRSA</td>
                  <td>AWS Systems Manager Parameter Store (Standard)</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (Free Standard Tier)</td>
                </tr>
                <tr>
                  <td><strong>Observability &amp; Metrics</strong></td>
                  <td>CloudWatch Container Insights</td>
                  <td>Prometheus Exporter + Grafana Dashboard</td>
                  <td><span style={{ color: '#10b981', fontWeight: 600 }}>$0.00</span> (Open-source)</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="alert-box alert-info" style={{ marginTop: '20px' }}>
            <span>
              💡 <strong>Pro-Tip for Indian Students:</strong> Never spin up <strong>Amazon MSK</strong> or <strong>Managed NAT Gateways</strong> on a personal card. They incur fixed hourly charges of ~$150-$200/month and ~$32/month respectively that cannot be stopped without deletion and are not covered by AWS Free Tier.
            </span>
          </div>
        </div>
      )}

      {/* Tab 2: Debit Card Verification Guide */}
      {activeTab === 'card' && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Indian Debit Card Verification &amp; ₹2 INR Refund Guide</h2>
              <p className="panel-desc">
                Detailed instructions for RBI-compliant card authentication under Amazon Web Services India Private Limited (AISPL).
              </p>
            </div>
          </div>

          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-card-title">Authorization Amount</div>
              <div className="metric-card-value" style={{ color: '#38bdf8' }}>₹2 INR</div>
              <div className="metric-card-subtitle">Temporary validation charge</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Refund Status</div>
              <div className="metric-card-value" style={{ color: '#10b981' }}>100% Refundable</div>
              <div className="metric-card-subtitle">Automated bank reversal</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Refund Reversal Time</div>
              <div className="metric-card-value" style={{ color: '#f59e0b' }}>5 - 7 Days</div>
              <div className="metric-card-subtitle">Credited back to bank account</div>
            </div>
          </div>

          <div style={{ marginTop: '24px' }}>
            <h3 style={{ fontSize: '16px', marginBottom: '12px', color: '#f8fafc' }}>
              Essential Debit Card Settings Checklist (Mobile Banking App)
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#1e293b', padding: '12px 16px', borderRadius: '8px' }}>
                <span style={{ color: '#10b981', fontSize: '18px' }}>✓</span>
                <div>
                  <strong>International Usage Enabled:</strong> In your mobile banking app (HDFC, SBI, ICICI, Axis, Kotak), navigate to Cards &gt; Manage Card &gt; Enable International Usage.
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#1e293b', padding: '12px 16px', borderRadius: '8px' }}>
                <span style={{ color: '#10b981', fontSize: '18px' }}>✓</span>
                <div>
                  <strong>Online / E-Commerce Transactions Enabled:</strong> Set the online POS/E-commerce limit to at least ₹100.
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#1e293b', padding: '12px 16px', borderRadius: '8px' }}>
                <span style={{ color: '#10b981', fontSize: '18px' }}>✓</span>
                <div>
                  <strong>Supported Card Networks:</strong> Visa, MasterCard, and American Express debit cards work reliably. Domestic-only RuPay cards often fail 3D Secure verification unless global payment is certified.
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: '#1e293b', padding: '12px 16px', borderRadius: '8px' }}>
                <span style={{ color: '#10b981', fontSize: '18px' }}>✓</span>
                <div>
                  <strong>Alternative Option (Zero Card Required):</strong> If you do not have an eligible international card, register at <strong>AWS Educate</strong> (aws.amazon.com/education/awseducate/) with your college or personal email for card-free cloud sandboxes.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 3: Safety Setup & AWS Account Status */}
      {activeTab === 'safety' && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">AWS Zero-Spend Safety Setup &amp; Account Status</h2>
              <p className="panel-desc">
                Enforcing strict ₹0 out-of-pocket usage charges, 100% local-first verification, and explicit authorization guardrails.
              </p>
            </div>
            <span className="badge badge-accepted" style={{ padding: '6px 12px' }}>
              ₹0 Target Enforced
            </span>
          </div>

          {/* Current Verified Account State */}
          <div className="metrics-grid" style={{ marginBottom: '24px' }}>
            <div className="metric-card">
              <div className="metric-card-title">AWS Account Plan</div>
              <div className="metric-card-value" style={{ color: '#38bdf8' }}>Free Tier</div>
              <div className="metric-card-subtitle">Active Free account tier</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Promotional Credits</div>
              <div className="metric-card-value" style={{ color: '#10b981' }}>$120.00</div>
              <div className="metric-card-subtitle">~183 days access remaining</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Current Amount Due</div>
              <div className="metric-card-value" style={{ color: '#34d399' }}>$0.00</div>
              <div className="metric-card-subtitle">Strict ₹0 out-of-pocket target</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Zero-Spend Alert Budget</div>
              <div className="metric-card-value" style={{ color: '#f59e0b' }}>$1.00</div>
              <div className="metric-card-subtitle">Email triggers at 50% ($0.50)</div>
            </div>
          </div>

          {/* Strict Pre-Deployment Protocol */}
          <div className="alert-box alert-info" style={{ marginBottom: '24px', borderColor: '#3b82f6' }}>
            <div>
              <strong style={{ color: '#93c5fd' }}>Mandatory Pre-Deployment Evaluation Protocol:</strong>
              <p style={{ margin: '6px 0 0', fontSize: '13px', lineHeight: 1.6 }}>
                To prevent accidental cloud charges, <strong>no cloud resources will ever be provisioned automatically</strong>. Before any AWS deployment is proposed:
              </p>
              <ol style={{ margin: '8px 0 0 20px', fontSize: '12px', lineHeight: 1.6 }}>
                <li><strong>Local-First Validation:</strong> 100% of pipeline benchmarks, chaos testing, and duplicate evaluations are executed locally at ₹0 cost.</li>
                <li><strong>Exact Service Itemization:</strong> Full breakdown of candidate services (compute, DB, broker) and exact Free-Tier credit limits.</li>
                <li><strong>Credit Coverage &amp; Expiry Risk:</strong> Explicitly distinguish between services covered by promotional credits and those with fixed hourly costs.</li>
                <li><strong>Zero-Charge Alternatives:</strong> Prioritize $0 services (EC2 t3/t4g micro, RDS db.t4g.micro, SQS FIFO, DynamoDB) over expensive managed offerings (MSK, NAT Gateways).</li>
              </ol>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', borderLeft: '4px solid #3b82f6' }}>
              <h4 style={{ color: '#93c5fd', marginBottom: '6px' }}>Step 1: Set up AWS Budgets ($1.00 Alert Threshold)</h4>
              <p style={{ fontSize: '13px', color: '#cbd5e1' }}>
                Navigate to <strong>AWS Billing Console &gt; Budgets &gt; Create Budget</strong>. Choose the <strong>Zero Spend Budget</strong> template or set a monthly cost budget of <strong>$1.00 USD</strong>. Add your email address to receive immediate alerts if spending exceeds $0.50 (50%).
              </p>
            </div>

            <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', borderLeft: '4px solid #10b981' }}>
              <h4 style={{ color: '#6ee7b7', marginBottom: '6px' }}>Step 2: Enable Free Tier Usage Alerts</h4>
              <p style={{ fontSize: '13px', color: '#cbd5e1' }}>
                In the Billing Preferences tab, check the box labeled <strong>Receive Free Tier Usage Alerts</strong>. AWS will email you automatically if any service reaches 85% of its monthly free allotment.
              </p>
            </div>

            <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', borderLeft: '4px solid #f59e0b' }}>
              <h4 style={{ color: '#fcd34d', marginBottom: '6px' }}>Step 3: Enable Multi-Factor Authentication (MFA)</h4>
              <p style={{ fontSize: '13px', color: '#cbd5e1' }}>
                Secure your Root User credentials immediately using an authenticator app (Google Authenticator, Microsoft Authenticator, or Authy). Never share root API access keys.
              </p>
            </div>

            <div style={{ background: '#1e293b', padding: '18px', borderRadius: '10px', borderLeft: '4px solid #a855f7' }}>
              <h4 style={{ color: '#d8b4fe', marginBottom: '6px' }}>Step 4: Create an IAM Dedicated Admin User</h4>
              <p style={{ fontSize: '13px', color: '#cbd5e1' }}>
                Create an IAM user named <code>student-admin</code> with AdministratorAccess. Log out of root and use this IAM user for everyday deployment tasks.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 4: Live Prometheus /metrics */}
      {activeTab === 'prometheus' && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Live Prometheus Telemetry Feed (/metrics)</h2>
              <p className="panel-desc">
                Production-grade OpenMetrics exposition format scraped by Prometheus, Grafana Agent, or AWS CloudWatch Container Insights.
              </p>
            </div>
            <button
              className="btn btn-secondary"
              onClick={fetchPrometheusMetrics}
              disabled={loadingMetrics}
            >
              {loadingMetrics ? 'Fetching...' : '🔄 Refresh Metrics'}
            </button>
          </div>

          <pre
            style={{
              background: '#090d16',
              padding: '16px',
              borderRadius: '8px',
              border: '1px solid #1f293d',
              color: '#34d399',
              fontFamily: 'monospace',
              fontSize: '12px',
              maxHeight: '400px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap',
            }}
          >
            {rawMetrics || 'Loading Prometheus metrics stream...'}
          </pre>
        </div>
      )}

      {/* Tab 5: Engine Config & Reset */}
      {activeTab === 'reset' && (
        <div className="panel">
          <div className="panel-header">
            <div>
              <h2 className="panel-title">Engine Configuration &amp; Demonstration Control</h2>
              <p className="panel-desc">
                View running parameters, inspect Bloom filter configuration, and reset state for clean test iterations.
              </p>
            </div>
          </div>

          {resetMsg && (
            <div className="alert-box alert-success" style={{ marginBottom: '20px' }}>
              <span>{resetMsg}</span>
            </div>
          )}

          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-card-title">Processing Mode</div>
              <div className="metric-card-value" style={{ color: '#60a5fa' }}>
                {summary?.mode || 'Direct'}
              </div>
              <div className="metric-card-subtitle">Zero-broker direct execution</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Bloom Window Slices</div>
              <div className="metric-card-value" style={{ color: '#a78bfa' }}>
                {summary?.bloom?.slices || 3}
              </div>
              <div className="metric-card-subtitle">Rotating bit arrays</div>
            </div>
            <div className="metric-card">
              <div className="metric-card-title">Hash Functions</div>
              <div className="metric-card-value" style={{ color: '#34d399' }}>
                {summary?.bloom?.hash_count || 7} k-hashes
              </div>
              <div className="metric-card-subtitle">Target FP rate: 1.0%</div>
            </div>
          </div>

          <div style={{ marginTop: '24px', padding: '20px', background: '#1e1b2e', borderRadius: '10px', border: '1px solid #4c1d95' }}>
            <h4 style={{ color: '#f43f5e', marginBottom: '8px' }}>Danger Zone: Reset Demo State</h4>
            <p style={{ fontSize: '13px', color: '#cbd5e1', marginBottom: '16px' }}>
              Resets all SQLite double-entry accounts, transactions, audit logs, DLQ events, and clears the in-memory Bloom filter. Use this before running fresh benchmarks.
            </p>
            <button
              className="btn btn-danger"
              onClick={handleReset}
              disabled={resetting}
            >
              {resetting ? 'Resetting...' : '⚠️ Reset All Demo Data'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
