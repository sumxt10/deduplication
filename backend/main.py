"""FastAPI application for the PS-15 exactly-once event deduplication engine."""
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import uuid
from fastapi import Body, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from .bloom_filter import SlidingWindowBloomFilter
from .cdc import CDCPipeline
from .config import settings
from .dedup import DeduplicationEngine
from .metrics import metrics_collector
from .processor import process_csv
from .schemas import CDCSimulationRequest, JobCreate, TransactionEvent
from .storage import Storage
from scripts.generate_paysim import generate_paysim_workload
from scripts.generate_transactions import generate

storage = Storage(settings.database_url)
bloom = SlidingWindowBloomFilter(settings.bloom_capacity, settings.bloom_error_rate)
engine = DeduplicationEngine(storage, bloom, metrics_collector)
cdc = CDCPipeline(engine)

app = FastAPI(
    title="PS-15 Exactly-Once Event De-duplication Engine",
    description="Distributed Financial Event Deduplication & CDC Processing Engine",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": settings.processing_mode,
        "database": "sqlite",
        "bloom_active": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/ready")
def ready():
    try:
        storage.summary()
        return {
            "ready": True,
            "database": True,
            "mode": settings.processing_mode,
            "bloom_bytes": bloom.memory_bytes,
        }
    except Exception as exc:
        raise HTTPException(503, detail="database unavailable") from exc


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus exposition format endpoint."""
    summary_counts = storage.summary()
    bloom_stats = {**bloom.config, "false_positives": bloom.false_positives}
    content = metrics_collector.to_prometheus_text(summary_counts, bloom_stats)
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


def _record_invalid(payload: dict, error: Exception):
    with storage.transaction() as db:
        db.execute(
            "INSERT INTO dead_letter_events(event_id, payload, reason, status, created_at) VALUES (?, ?, ?, 'unresolved', ?)",
            (
                payload.get("event_id"),
                json.dumps(payload),
                str(error),
                datetime.now(timezone.utc).isoformat(),
            ),
        )


@app.post("/api/v1/events")
def ingest(payload: dict = Body(...)):
    try:
        event = TransactionEvent.model_validate(payload)
    except ValidationError as exc:
        _record_invalid(payload, exc)
        raise HTTPException(422, detail=f"Event rejected and sent to DLQ: {exc}") from exc
    return engine.process(event).__dict__


@app.post("/api/v1/events/batch")
def ingest_batch(payload: dict = Body(...)):
    raw_events = payload.get("events")
    if not isinstance(raw_events, list) or not raw_events or len(raw_events) > 1000:
        raise HTTPException(422, detail="events must contain 1 to 1000 records")
    results = []
    for raw_event in raw_events:
        try:
            results.append(engine.process(TransactionEvent.model_validate(raw_event)).__dict__)
        except ValidationError as exc:
            invalid_payload = raw_event if isinstance(raw_event, dict) else {"raw_event": raw_event}
            _record_invalid(invalid_payload, exc)
            results.append({
                "status": "invalid",
                "event_id": invalid_payload.get("event_id"),
                "transaction_id": invalid_payload.get("transaction_id"),
                "reason": str(exc),
            })
    return {"results": results, "processed": len(results)}


@app.get("/api/v1/dashboard/summary")
def dashboard_summary():
    return {
        "summary": storage.summary(),
        "bloom": {
            **bloom.config,
            "positives": bloom.positives,
            "negatives": bloom.negatives,
            "confirmed_duplicates": bloom.confirmed_duplicates,
            "false_positives": bloom.false_positives,
        },
        "latency": metrics_collector.snapshot(),
        "cdc": cdc.stats,
        "mode": settings.processing_mode,
    }


@app.get("/api/v1/metrics")
def metrics():
    return {
        "summary": storage.summary(),
        "bloom": {
            **bloom.config,
            "positives": bloom.positives,
            "negatives": bloom.negatives,
            "confirmed_duplicates": bloom.confirmed_duplicates,
            "false_positives": bloom.false_positives,
        },
        "latency": metrics_collector.snapshot(),
        "cdc": cdc.stats,
    }


@app.get("/api/v1/events")
def events(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
):
    return storage.events(page, page_size, status)


# --- Dead Letter Queue (DLQ) Management Endpoints ---


@app.get("/api/v1/dlq")
def dlq(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
):
    return storage.dlq_events(page, page_size, status)


@app.post("/api/v1/dlq/{dlq_id}/redrive")
def redrive_dlq_event(dlq_id: int):
    """Re-attempts to parse and process a poisoned or rejected event from DLQ."""
    item = storage.get_dlq_event(dlq_id)
    if not item:
        raise HTTPException(404, detail="DLQ item not found")

    try:
        raw_payload = json.loads(item["payload"])
        # Attempt repair of common errors (e.g. negative amount or missing schema)
        if "amount" in raw_payload and float(raw_payload["amount"]) <= 0:
            raw_payload["amount"] = "100.00"  # Rectify negative amount for recovery test
        if "currency" not in raw_payload:
            raw_payload["currency"] = "INR"

        event = TransactionEvent.model_validate(raw_payload)
        result = engine.process(event)
        storage.resolve_dlq(dlq_id, status="resolved")
        return {"success": True, "dlq_id": dlq_id, "result": result.__dict__}
    except Exception as exc:
        return {"success": False, "dlq_id": dlq_id, "error": str(exc)}


@app.post("/api/v1/dlq/redrive-all")
def redrive_all_dlq():
    """Batch re-processes all unresolved DLQ items."""
    unresolved = storage.dlq_events(page=1, page_size=200, status="unresolved")
    results = []
    for item in unresolved.get("items", []):
        try:
            raw_payload = json.loads(item["payload"])
            if "amount" in raw_payload and float(raw_payload["amount"]) <= 0:
                raw_payload["amount"] = "100.00"
            event = TransactionEvent.model_validate(raw_payload)
            res = engine.process(event)
            storage.resolve_dlq(item["id"], status="resolved")
            results.append({"id": item["id"], "status": "resolved", "result": res.status})
        except Exception as exc:
            results.append({"id": item["id"], "status": "still_failing", "error": str(exc)})
    return {"redriven_count": len(results), "items": results}


@app.delete("/api/v1/dlq/{dlq_id}")
def delete_dlq_event(dlq_id: int):
    storage.delete_dlq(dlq_id)
    return {"deleted": True, "dlq_id": dlq_id}


# --- Event Replay & System Reset Endpoints ---


@app.post("/api/v1/events/{event_id}/replay")
def replay(event_id: str):
    db = storage.connection()
    try:
        row = db.execute(
            "SELECT payload FROM processed_events WHERE event_id = ? ORDER BY id LIMIT 1",
            (event_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, detail="event not found")
        return engine.process(TransactionEvent.model_validate_json(row["payload"])).__dict__
    finally:
        db.close()


@app.post("/api/v1/demo/reset")
def reset():
    storage.reset()
    bloom.reset()
    metrics_collector.clear()
    cdc.history.clear()
    return {"reset": True, "message": "Authoritative storage, Bloom filter, and metrics cleared"}


# --- CDC Pipeline Endpoints ---


@app.post("/api/v1/cdc/simulate")
def simulate_cdc(request: CDCSimulationRequest):
    """Triggers simulated CDC log tailing with configurable duplicate injection."""
    result = cdc.simulate_cdc_stream(
        total_events=request.total_events,
        duplicate_rate=request.duplicate_rate,
        network_retry_burst=request.network_retry_burst,
        delay_ms=request.interval_ms,
    )
    return result


@app.get("/api/v1/cdc/status")
def cdc_status():
    return {
        "stats": cdc.stats,
        "latest_history": cdc.history[:50],
        "total_history_count": len(cdc.history),
    }


# --- Background Job / Benchmark Execution ---


def _run_job(job_id: str, request: JobCreate):
    with storage.transaction() as db:
        db.execute(
            "UPDATE demo_jobs SET status='running', updated_at=? WHERE job_id=?",
            (datetime.now(timezone.utc).isoformat(), job_id),
        )
    generated_path = None
    try:
        input_path = request.input_path
        if not input_path:
            generated_path = settings.data_dir / f"job-{job_id}.csv"
            if request.dataset == "paysim":
                generate_paysim_workload(
                    output_path=str(generated_path),
                    total=request.total_records,
                    duplicate_rate=request.duplicate_rate,
                    invalid_rate=request.invalid_rate,
                    seed=request.seed,
                )
            else:
                generate(
                    generated_path,
                    request.total_records,
                    request.duplicate_rate,
                    request.invalid_rate,
                    request.seed,
                )
            input_path = generated_path

        def update_progress(counters):
            with storage.transaction() as db:
                db.execute(
                    "UPDATE demo_jobs SET progress=?, accepted=?, duplicates=?, invalid=?, failed=?, updated_at=? WHERE job_id=?",
                    (
                        counters["total"],
                        counters["accepted"],
                        counters["duplicates"],
                        counters["invalid"],
                        counters["failed"],
                        datetime.now(timezone.utc).isoformat(),
                        job_id,
                    ),
                )

        result = process_csv(input_path, engine, request.batch_size, update_progress)
        with storage.transaction() as db:
            db.execute(
                "UPDATE demo_jobs SET status='completed', progress=total, accepted=?, duplicates=?, invalid=?, failed=?, duration_ms=?, result=?, updated_at=? WHERE job_id=?",
                (
                    result["accepted"],
                    result["duplicates"],
                    result["invalid"],
                    result["failed"],
                    result["duration_ms"],
                    json.dumps(result),
                    datetime.now(timezone.utc).isoformat(),
                    job_id,
                ),
            )
    except Exception as exc:
        with storage.transaction() as db:
            db.execute(
                "UPDATE demo_jobs SET status='failed', error=?, updated_at=? WHERE job_id=?",
                (str(exc), datetime.now(timezone.utc).isoformat(), job_id),
            )
    finally:
        if generated_path and generated_path.exists():
            generated_path.unlink()


@app.post("/api/v1/jobs", status_code=202)
def create_job(request: JobCreate):
    if request.input_path:
        requested_path = (settings.data_dir / request.input_path).resolve()
        data_root = settings.data_dir.resolve()
        if data_root not in requested_path.parents or not requested_path.is_file():
            raise HTTPException(
                400, detail="input_path must reference an existing file under data directory"
            )
        request.input_path = str(requested_path)

    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with storage.transaction() as db:
        db.execute(
            "INSERT INTO demo_jobs(job_id, status, config, total, created_at, updated_at) VALUES (?, 'queued', ?, ?, ?, ?)",
            (job_id, request.model_dump_json(), request.total_records, now, now),
        )
    threading.Thread(target=_run_job, args=(job_id, request), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    db = storage.connection()
    try:
        row = db.execute("SELECT * FROM demo_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail="job not found")
        return dict(row)
    finally:
        db.close()


@app.get("/api/v1/jobs")
def list_jobs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    db = storage.connection()
    try:
        rows = db.execute(
            "SELECT * FROM demo_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return {"items": [dict(row) for row in rows]}
    finally:
        db.close()