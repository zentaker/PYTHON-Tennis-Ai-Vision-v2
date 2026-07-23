from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str = Field(examples=["SESSION_NOT_FOUND"])
    message: str = Field(examples=["session not found"])
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str = Field(examples=["2f9e4f25-9d45-4e04-a5e7-8dd3b6c2d310"])


class ErrorResponse(BaseModel):
    error: ErrorPayload
