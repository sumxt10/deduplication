from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=128)
    transaction_id: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    sender_account: str = Field(min_length=1, max_length=64)
    receiver_account: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    transaction_type: Literal["transfer"] = "transfer"
    schema_version: int = Field(default=1, ge=1)
    source: str = Field(default="direct", min_length=1, max_length=64)
    delivery_attempt: int = Field(default=1, ge=1)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        value = value.upper()
        if value != "INR":
            raise ValueError("only INR is supported in local mode")
        return value

    @field_validator("schema_version")
    @classmethod
    def supported_schema_version(cls, value: int) -> int:
        if value != 1:
            raise ValueError("unsupported schema_version")
        return value

    @field_validator("timestamp")
    @classmethod
    def timestamp_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("receiver_account")
    @classmethod
    def different_accounts(cls, value: str, info):
        sender = info.data.get("sender_account")
        if sender and sender == value:
            raise ValueError("sender and receiver must differ")
        return value


class BatchEvents(BaseModel):
    events: list[TransactionEvent] = Field(min_length=1, max_length=1000)


class JobCreate(BaseModel):
    input_path: str | None = None
    total_records: int = Field(default=1000, ge=1, le=1_000_000)
    duplicate_rate: float = Field(default=0.30, ge=0, lt=1)
    invalid_rate: float = Field(default=0.01, ge=0, lt=1)
    seed: int = 42
    batch_size: int = Field(default=500, ge=1, le=5000)
    mode: Literal["direct"] = "direct"

    @field_validator("invalid_rate")
    @classmethod
    def rates_fit(cls, value: float, info):
        if info.data.get("duplicate_rate", 0) + value >= 1:
            raise ValueError("duplicate_rate + invalid_rate must be less than 1")
        return value