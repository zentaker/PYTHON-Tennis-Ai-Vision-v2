from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .interface import ObjectHead, PresignedObject
from .keys import validate_object_key


class S3ObjectStorage:
    def __init__(self, settings) -> None:
        import boto3

        self.settings = settings
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )

    def _key(self, key: str) -> str:
        return validate_object_key(key)

    def _expires(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(
            seconds=self.settings.s3_presign_expires_seconds
        )

    def create_presigned_upload(self, key: str, content_type: str) -> PresignedObject:
        key = self._key(key)
        expires = self.settings.s3_presign_expires_seconds
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )
        return PresignedObject(url, "PUT", {"Content-Type": content_type}, self._expires())

    def create_presigned_download(
        self, key: str, content_type: str | None = None
    ) -> PresignedObject:
        key = self._key(key)
        expires = self.settings.s3_presign_expires_seconds
        params = {"Bucket": self.settings.s3_bucket, "Key": key}
        if content_type:
            params["ResponseContentType"] = content_type
        url = self.client.generate_presigned_url("get_object", Params=params, ExpiresIn=expires)
        return PresignedObject(url, "GET", {}, self._expires())

    def head_object(self, key: str) -> ObjectHead:
        key = self._key(key)
        response = self.client.head_object(Bucket=self.settings.s3_bucket, Key=key)
        return ObjectHead(
            key, int(response["ContentLength"]), response.get("ContentType"), response.get("ETag")
        )

    def delete_object(self, key: str) -> None:
        self.client.delete_object(Bucket=self.settings.s3_bucket, Key=self._key(key))

    def object_exists(self, key: str) -> bool:
        try:
            self.head_object(key)
        except self.client.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def put_bytes(self, key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.settings.s3_bucket, Key=self._key(key), Body=body, ContentType=content_type
        )

    def get_bytes(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.settings.s3_bucket, Key=self._key(key))[
            "Body"
        ].read()
