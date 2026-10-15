"""FastAPI application for the local PS-15 exactly-once demonstration."""
import json
import threading
import uuid
from datetime import datetime, timezone
from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .bloom_filter import SlidingWindowBloomFilter
from .config import settings
from .dedup import DeduplicationEngine
from .processor import process_csv
from pydantic import ValidationError
from .schemas import JobCreate, TransactionEvent
from .storage import Storage
from scripts.generate_transactions import generate

storage = Storage(settings.database_url)
bloom = SlidingWindowBloomFilter(settings.bloom_capacity, settings.bloom_error_rate)
engine = DeduplicationEngine(storage, bloom)
app = FastAPI(title="PS-15 Event Deduplication Engine", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.processing_mode, "database": "sqlite"}


@app.get("/health/ready")
def ready():
    try:
        storage.summary()
        return {"ready": True, "database": True, "mode": settings.processing_mode}
    except Exception as exc:
        raise HTTPException(503, detail="database unavailable") from exc


def _record_invalid(payload, error):
    with storage.transaction() as db:
        db.execute("INSERT INTO dead_letter_events(event_id, payload, reason, created_at) VALUES (?, ?, ?, ?)",
                   (payload.get("event_id"), json.dumps(payload), str(error),
                    datetime.now(timezone.utc).isoformat()))


@app.post("/api/v1/events")
def ingest(payload: dict = Body(...)):
    try:
        event = TransactionEvent.model_validate(payload)
    except ValidationError as exc:
        _record_invalid(payload, exc)
        raise HTTPException(422, detail="event rejected and recorded in dead-letter queue") from exc
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
            results.append({"status": "invalid",
                            "event_id": invalid_payload.get("event_id"),
                            "transaction_id": invalid_payload.get("transaction_id"),
                            "reason": "event rejected"})
    return {"results": results}


@app.get("/api/v1/dashboard/summary")
def dashboard_summary():
    return {"summary": storage.summary(), "bloom": bloom.config, "mode": settings.processing_mode}


@app.get("/api/v1/metrics")
def metrics():
    return {"summary": storage.summary(),
            "bloom": {**bloom.config, "positives": bloom.positives,
                      "negatives": bloom.negatives, "confirmed_duplicates": bloom.confirmed_duplicates,
                      "false_positives": bloom.false_positives}}


@app.get("/api/v1/events")
def events(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
           status: str | None = None):
    return storage.events(page, page_size, status)


@app.get("/api/v1/dlq")
def dlq(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200)):
    db = storage.connection()
    try:
        rows = db.execute("SELECT * FROM dead_letter_events ORDER BY id DESC LIMIT ? OFFSET ?",
                          (page_size, (page - 1) * page_size)).fetchall()
        total = db.execute("SELECT COUNT(*) FROM dead_letter_events").fetchone()[0]
        return {"items": [dict(row) for row in rows], "total": total, "page": page, "page_size": page_size}
    finally:
        db.close()


@app.post("/api/v1/events/{event_id}/replay")
def replay(event_id: str):
    db = storage.connection()
    try:
        row = db.execute("SELECT payload FROM processed_events WHERE event_id = ? ORDER BY id LIMIT 1",
                         (event_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail="event not found")
        return engine.process(TransactionEvent.model_validate_json(row["payload"])).__dict__
    finally:
        db.close()


@app.post("/api/v1/demo/reset")
def reset():
    storage.reset()
    bloom.reset()
    return {"reset": True}


def _run_job(job_id, request):
    with storage.transaction() as db:
        db.execute("UPDATE demo_jobs SET status='running', updated_at=? WHERE job_id=?",
                   (datetime.now(timezone.utc).isoformat(), job_id))
    try:
        input_path = request.input_path
        generated_path = None
        if not input_path:
            generated_path = settings.data_dir / f"job-{job_id}.csv"
            generate(generated_path, request.total_records, request.duplicate_rate,
                     request.invalid_rate, request.seed)
            input_path = generated_path
        def update_progress(counters):
            with storage.transaction() as db:
                db.execute("UPDATE demo_jobs SET progress=?, accepted=?, duplicates=?, invalid=?, failed=?, updated_at=? WHERE job_id=?",
                           (counters["total"], counters["accepted"], counters["duplicates"],
                            counters["invalid"], counters["failed"],
                            datetime.now(timezone.utc).isoformat(), job_id))

        result = process_csv(input_path, engine, request.batch_size, update_progress)
        with storage.transaction() as db:
            db.execute("UPDATE demo_jobs SET status='completed', progress=total, accepted=?, duplicates=?, invalid=?, failed=?, duration_ms=?, result=?, updated_at=? WHERE job_id=?",
                       (result["accepted"], result["duplicates"], result["invalid"], result["failed"],
                        result["duration_ms"], json.dumps(result),
                        datetime.now(timezone.utc).isoformat(), job_id))
    except Exception as exc:
        with storage.transaction() as db:
            db.execute("UPDATE demo_jobs SET status='failed', error=?, updated_at=? WHERE job_id=?",
                       (str(exc), datetime.now(timezone.utc).isoformat(), job_id))
    finally:
        if generated_path and generated_path.exists():
            generated_path.unlink()


@app.post("/api/v1/jobs", status_code=202)
def create_job(request: JobCreate):
    if request.input_path:
        requested_path = (settings.data_dir / request.input_path).resolve()
        data_root = settings.data_dir.resolve()
        if data_root not in requested_path.parents or not requested_path.is_file():
            raise HTTPException(400, detail="input_path must reference an existing file under the data directory")
        request.input_path = str(requested_path)
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with storage.transaction() as db:
        db.execute("INSERT INTO demo_jobs(job_id,status,config,total,created_at,updated_at) VALUES (?, 'queued', ?, ?, ?, ?)",
                   (job_id, request.model_dump_json(), request.total_records, now, now))
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
        rows = db.execute("SELECT * FROM demo_jobs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                          (page_size, (page - 1) * page_size)).fetchall()
        return {"items": [dict(row) for row in rows]}
    finally:
        db.close()