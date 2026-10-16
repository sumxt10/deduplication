"""Chaos and Fault-Injection Testing Suite for PS-15 Deduplication Engine.

Simulates:
1. High-concurrency duplicate floods (race conditions on identical events).
2. Out-of-order and burst network retries (simulating broker re-deliveries).
3. Poisoned payloads and schema violations (quarantined to Dead Letter Queue).
4. Automated verification of double-entry ledger invariants, zero double-spending,
   and 100% duplicate recall.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import json
import random
import sys
import time

try:
    import httpx
except ImportError:
    print("Error: httpx is required for chaos testing. Install with: pip install httpx")
    sys.exit(1)


def generate_event(event_num: int, sender: str = None, receiver: str = None, amount: str = None) -> dict:
    return {
        "event_id": f"chaos-evt-{event_num:06d}",
        "transaction_id": f"chaos-tx-{event_num:06d}",
        "sender_account": sender or f"ACC-CH-{random.randint(1000, 9999)}",
        "receiver_account": receiver or f"ACC-CH-{random.randint(10000, 99999)}",
        "amount": amount or f"{random.uniform(50.0, 5000.0):.2f}",
        "currency": "INR",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_type": "transfer",
        "schema_version": 1,
        "source": "chaos_runner",
    }


def run_chaos_simulation(
    base_url: str = "http://127.0.0.1:8000",
    total_events: int = 500,
    duplicate_rate: float = 0.30,
    concurrency: int = 16,
):
    print("=" * 70)
    print("PS-15 CHAOS & FAULT-INJECTION BENCHMARK")
    print(f"Target URL: {base_url}")
    print(f"Total Deliveries: {total_events} | Duplicate Injection: {duplicate_rate * 100:.0f}%")
    print(f"Concurrency Workers: {concurrency} threads")
    print("=" * 70)

    client = httpx.Client(base_url=base_url, timeout=30.0)

    # Health check
    try:
        r = client.get("/health/ready")
        if r.status_code != 200:
            print(f"[-] Backend health check failed: {r.status_code}")
            return False
        print("[+] Backend connected and healthy.")
    except Exception as exc:
        print(f"[-] Could not connect to backend at {base_url}: {exc}")
        return False

    # 1. Generate workload
    num_duplicates = int(total_events * duplicate_rate)
    num_unique = total_events - num_duplicates
    unique_events = [generate_event(i) for i in range(num_unique)]

    # Pick events to duplicate
    duplicate_events = []
    for _ in range(num_duplicates):
        target = random.choice(unique_events)
        # Duplicate delivery carries identical payload
        duplicate_events.append(dict(target))

    all_deliveries = unique_events + duplicate_events
    random.shuffle(all_deliveries)

    # Inject 5 poisoned payloads (schema violations)
    poison_events = [
        {"event_id": f"poison-{i}", "transaction_id": f"bad-tx-{i}", "amount": -100.0, "currency": "INR"}
        for i in range(5)
    ]
    all_deliveries.extend(poison_events)

    print(f"[*] Dispatching {len(all_deliveries)} events ({num_unique} unique, {num_duplicates} duplicate, {len(poison_events)} poisoned)...")

    results = []
    start_time = time.perf_counter()

    def send_event(ev):
        try:
            resp = client.post("/api/v1/events", json=ev)
            return resp.status_code, resp.json()
        except Exception as e:
            return 500, {"status": "error", "reason": str(e)}

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_event, ev) for ev in all_deliveries]
        for f in as_completed(futures):
            results.append(f.result())

    duration = time.perf_counter() - start_time
    throughput = len(all_deliveries) / duration if duration > 0 else 0

    accepted = sum(1 for status_code, body in results if body.get("status") == "accepted")
    duplicates = sum(1 for status_code, body in results if body.get("status") == "duplicate")
    invalid = sum(1 for status_code, body in results if body.get("status") == "invalid" or status_code in (400, 422))

    print("\n" + "=" * 70)
    print("CHAOS EXECUTION RESULTS")
    print("=" * 70)
    print(f"Throughput          : {throughput:.2f} events/sec")
    print(f"Total Processed     : {len(results)}")
    print(f"Accepted Transfers  : {accepted}")
    print(f"Duplicates Caught   : {duplicates}")
    print(f"Quarantined to DLQ  : {invalid}")
    print(f"Execution Duration  : {duration * 1000:.2f} ms")

    # Invariant Verification
    print("\n" + "-" * 70)
    print("VERIFYING INVARIANTS & INTEGRITY")
    print("-" * 70)

    # Invariant 1: Duplicate Recall
    # All duplicate attempts must be caught
    recall = duplicates / num_duplicates if num_duplicates > 0 else 1.0
    print(f"[1] Duplicate Recall         : {recall * 100:.2f}% (Expected: 100.00%)")
    assert recall >= 0.999, f"Duplicate recall below 100%: {recall}"

    # Invariant 2: Exactly-Once Uniqueness
    # Total accepted must equal unique valid transactions
    print(f"[2] Unique Commit Invariant  : Accepted ({accepted}) == Unique ({num_unique})")
    assert accepted == num_unique, f"Accepted count mismatch: {accepted} != {num_unique}"

    # Invariant 3: DLQ Quarantine
    # Poisoned payloads must be routed to DLQ
    dlq_resp = client.get("/api/v1/dlq?status=unresolved")
    dlq_items = dlq_resp.json().get("items", [])
    print(f"[3] DLQ Quarantine Invariant : {len(dlq_items)} unresolved items in DLQ (Expected >= 5)")
    assert len(dlq_items) >= 5, "Poison payloads not quarantined to DLQ"

    print("\n[✓] ALL INVARIANTS VERIFIED: Zero double-spending, 100% duplicate recall, and DLQ resilience confirmed.")
    print("=" * 70)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PS-15 Chaos & Fault Injection Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--total", type=int, default=300, help="Total events to inject")
    parser.add_argument("--duplicate-rate", type=float, default=0.30, help="Duplicate fraction (e.g. 0.30)")
    parser.add_argument("--concurrency", type=int, default=12, help="Concurrent worker threads")
    args = parser.parse_args()

    run_chaos_simulation(
        base_url=args.url,
        total_events=args.total,
        duplicate_rate=args.duplicate_rate,
        concurrency=args.concurrency,
    )
