from fastapi.testclient import TestClient
from backend.main import app


def test_health():
    assert TestClient(app).get("/health").status_code == 200


def test_invalid_event_is_counted_and_isolated():
    client = TestClient(app)
    client.post("/api/v1/demo/reset")
    response = client.post("/api/v1/events", json={
        "event_id": "invalid", "transaction_id": "invalid-tx",
        "timestamp": "2025-01-01T00:00:00Z", "sender_account": "a",
        "receiver_account": "b", "amount": "-1", "currency": "INR",
        "transaction_type": "transfer", "schema_version": 1, "source": "test",
    })
    assert response.status_code == 422
    summary = client.get("/api/v1/dashboard/summary").json()["summary"]
    assert summary["total_deliveries"] == 1
    assert summary["invalid"] == 1


def test_batch_keeps_valid_events_when_one_record_is_invalid():
    client = TestClient(app)
    client.post("/api/v1/demo/reset")
    valid = {
        "event_id": "valid", "transaction_id": "valid-tx",
        "timestamp": "2025-01-01T00:00:00Z", "sender_account": "a",
        "receiver_account": "b", "amount": "10.00", "currency": "INR",
        "transaction_type": "transfer", "schema_version": 1, "source": "test",
    }
    invalid = {**valid, "event_id": "bad", "transaction_id": "bad-tx", "amount": "-1"}
    response = client.post("/api/v1/events/batch", json={"events": [valid, invalid]})
    assert [item["status"] for item in response.json()["results"]] == ["accepted", "invalid"]
    assert client.get("/api/v1/dashboard/summary").json()["summary"]["transactions"] == 1


def test_batch_quarantines_non_object_payload():
    client = TestClient(app)
    client.post("/api/v1/demo/reset")
    response = client.post("/api/v1/events/batch", json={"events": ["not-an-event"]})
    assert response.status_code == 200
    assert response.json()["results"][0]["status"] == "invalid"