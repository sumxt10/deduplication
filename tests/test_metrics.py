from backend.metrics import LatencyTracker, MetricsCollector, percentile


def test_percentile_calculation():
    # 100 values from 1 to 100
    vals = list(range(1, 101))
    p50 = percentile(vals, 0.50)
    p95 = percentile(vals, 0.95)
    p99 = percentile(vals, 0.99)

    assert 49 <= p50 <= 51
    assert 94 <= p95 <= 96
    assert 98 <= p99 <= 100


def test_latency_tracker_and_collector():
    collector = MetricsCollector()
    collector.record(total_us=1500.0, fp_us=200.0, bloom_us=100.0, storage_us=1200.0)
    collector.record(total_us=2500.0, fp_us=300.0, bloom_us=150.0, storage_us=2050.0)

    snap = collector.snapshot()
    assert snap["total_latency"]["count"] == 2
    assert snap["total_latency"]["p50_us"] > 0
    assert snap["fingerprint_latency"]["p50_us"] > 0

    prom_text = collector.to_prometheus_text(
        summary_counts={"total_deliveries": 10, "accepted": 8, "duplicates": 2, "invalid": 0},
        bloom_stats={"memory_bytes": 1024, "false_positives": 0},
    )
    assert "ps15_deliveries_total 10" in prom_text
    assert "ps15_accepted_transactions_total 8" in prom_text
    assert 'ps15_latency_ms{quantile="0.50",stage="total"}' in prom_text
