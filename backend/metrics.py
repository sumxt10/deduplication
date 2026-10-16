"""Metrics and latency percentile tracking for the deduplication pipeline."""
from collections import deque
from statistics import quantiles
import threading
import time


def percentile(values, fraction):
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    sorted_vals = sorted(values)
    return quantiles(sorted_vals, n=100, method="inclusive")[max(0, int(fraction * 100) - 1)]


class LatencyTracker:
    def __init__(self, max_samples: int = 10_000):
        self.max_samples = max_samples
        self._samples = deque(maxlen=max_samples)
        self._lock = threading.Lock()

    def record(self, latency_us: float):
        with self._lock:
            self._samples.append(latency_us)

    def stats(self):
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return {
                "count": 0,
                "p50_us": 0.0,
                "p95_us": 0.0,
                "p99_us": 0.0,
                "avg_us": 0.0,
                "min_us": 0.0,
                "max_us": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "avg_ms": 0.0,
            }
        p50 = percentile(samples, 0.50)
        p95 = percentile(samples, 0.95)
        p99 = percentile(samples, 0.99)
        avg = sum(samples) / len(samples)
        return {
            "count": len(samples),
            "p50_us": round(p50, 2),
            "p95_us": round(p95, 2),
            "p99_us": round(p99, 2),
            "avg_us": round(avg, 2),
            "min_us": round(min(samples), 2),
            "max_us": round(max(samples), 2),
            "p50_ms": round(p50 / 1000.0, 3),
            "p95_ms": round(p95 / 1000.0, 3),
            "p99_ms": round(p99 / 1000.0, 3),
            "avg_ms": round(avg / 1000.0, 3),
        }

    def clear(self):
        with self._lock:
            self._samples.clear()


class MetricsCollector:
    def __init__(self, max_samples: int = 10_000):
        self.total = LatencyTracker(max_samples)
        self.fingerprint = LatencyTracker(max_samples)
        self.bloom = LatencyTracker(max_samples)
        self.storage = LatencyTracker(max_samples)

    def record(self, total_us: float, fp_us: float, bloom_us: float, storage_us: float):
        self.total.record(total_us)
        self.fingerprint.record(fp_us)
        self.bloom.record(bloom_us)
        self.storage.record(storage_us)

    def snapshot(self):
        return {
            "total_latency": self.total.stats(),
            "fingerprint_latency": self.fingerprint.stats(),
            "bloom_latency": self.bloom.stats(),
            "storage_latency": self.storage.stats(),
        }

    def clear(self):
        self.total.clear()
        self.fingerprint.clear()
        self.bloom.clear()
        self.storage.clear()

    def to_prometheus_text(self, summary_counts: dict, bloom_stats: dict) -> str:
        snap = self.snapshot()
        tot = snap["total_latency"]
        lines = [
            "# HELP ps15_deliveries_total Total transaction events ingested",
            "# TYPE ps15_deliveries_total counter",
            f"ps15_deliveries_total {summary_counts.get('total_deliveries', 0)}",
            "# HELP ps15_accepted_transactions_total Successfully committed transactions",
            "# TYPE ps15_accepted_transactions_total counter",
            f"ps15_accepted_transactions_total {summary_counts.get('accepted', 0)}",
            "# HELP ps15_duplicate_events_total Duplicate events detected and prevented",
            "# TYPE ps15_duplicate_events_total counter",
            f"ps15_duplicate_events_total {summary_counts.get('duplicates', 0)}",
            "# HELP ps15_dead_letter_events_total Malformed or invalid events routed to DLQ",
            "# TYPE ps15_dead_letter_events_total counter",
            f"ps15_dead_letter_events_total {summary_counts.get('invalid', 0)}",
            "# HELP ps15_bloom_memory_bytes Memory allocated for sliding-window Bloom filter",
            "# TYPE ps15_bloom_memory_bytes gauge",
            f"ps15_bloom_memory_bytes {bloom_stats.get('memory_bytes', 0)}",
            "# HELP ps15_bloom_false_positives_total False positive screenings recorded",
            "# TYPE ps15_bloom_false_positives_total counter",
            f"ps15_bloom_false_positives_total {bloom_stats.get('false_positives', 0)}",
            "# HELP ps15_latency_ms Latency percentiles in milliseconds",
            "# TYPE ps15_latency_ms gauge",
            f'ps15_latency_ms{{quantile="0.50",stage="total"}} {tot.get("p50_ms", 0.0)}',
            f'ps15_latency_ms{{quantile="0.95",stage="total"}} {tot.get("p95_ms", 0.0)}',
            f'ps15_latency_ms{{quantile="0.99",stage="total"}} {tot.get("p99_ms", 0.0)}',
            f'ps15_latency_ms{{quantile="avg",stage="total"}} {tot.get("avg_ms", 0.0)}',
        ]
        return "\n".join(lines) + "\n"


metrics_collector = MetricsCollector()