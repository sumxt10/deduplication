# PS-15 project structure

* `backend/` contains the FastAPI application, Pydantic event schema, canonical SHA-256 fingerprinting, rotating Bloom filter, SQLite atomic storage, processor, and optional Kafka worker.
* `frontend/` contains the Vite React operations console.
* `scripts/generate_transactions.py` creates deterministic streaming CSV workloads with ground-truth labels.
* `tests/` contains unit and API tests.
* `data/` is the local runtime data directory and is intentionally ignored except for `.gitkeep`.
* `docker-compose.yml` runs the local containerized frontend and backend. Kubernetes manifests are optional local-cluster deployment material.
* `k8s/` contains probe-enabled backend/frontend services and an opt-in Kafka worker deployment (`replicas: 0` until a broker and shared database are configured).