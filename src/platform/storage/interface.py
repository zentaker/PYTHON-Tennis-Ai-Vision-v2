from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class PresignedObject:
    url: str
    method: str
    headers: dict[str, str]
    expires_at: datetime


@dataclass(frozen=True)
class ObjectHead:
    key: str
    size_bytes: int
    content_type: str | None
    etag: str | None


class ObjectStorage(Protocol):
    def create_presigned_upload(self, key: str, content_type: str) -> PresignedObject: ...

    def create_presigned_download(
        self, key: str, content_type: str | None = None
    ) -> PresignedObject: ...

    def head_object(self, key: str) -> ObjectHead: ...

    def delete_object(self, key: str) -> None: ...

    def object_exists(self, key: str) -> bool: ...

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None: ...

    def get_bytes(self, key: str) -> bytes: ...

    def bucket_exists(self) -> bool: ...
