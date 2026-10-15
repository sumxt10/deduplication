"""Environment-backed application configuration."""
from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/ps15.db")
    processing_mode: str = os.getenv("PROCESSING_MODE", "direct")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
    bloom_capacity: int = int(os.getenv("BLOOM_CAPACITY", "100000"))
    bloom_error_rate: float = float(os.getenv("BLOOM_ERROR_RATE", "0.001"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "500"))


settings = Settings()
