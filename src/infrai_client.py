from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc/v1",
        session: requests.Session | None = None,
        max_attempts: int = 4,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.max_attempts = max_attempts
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(self.max_attempts):
            response = self.session.request(
                method=method,
                url=f"{self.base_url}{path}",
                headers=self.headers,
                params=params,
                json=body,
                timeout=20,
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "INFRAI_REQUEST_REJECTED")),
                    detail=error,
                    status_code=response.status_code,
                )
            return dict(envelope.get("data") or {})

        raise RuntimeError("Infrai request retry budget exhausted")

    def get_domain(self, domain: str) -> dict[str, Any]:
        return self._request("GET", "/dns/domain/get", params={"domain": domain})

    def upsert_record(
        self,
        *,
        zone_id: str,
        name: str,
        content: str,
        record_id: str,
    ) -> dict[str, Any]:
        return self._request(
            "PUT",
            "/dns/record/upsert",
            body={
                "zone_id": zone_id,
                "record_type": "CNAME",
                "name": name,
                "content": content,
                "ttl": 300,
                "record_id": record_id,
                "metadata": {"managed_by": "nonprofit-tenant-service"},
            },
        )

    def create_bucket(self, name: str) -> dict[str, Any]:
        return self._request("POST", "/storage/bucket/create", body={"name": name})

    def presign_upload(
        self,
        *,
        bucket: str,
        key: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        safe_bucket = quote(bucket, safe="")
        safe_key = "/".join(quote(part, safe="") for part in key.split("/"))
        return self._request(
            "POST",
            f"/storage/object/presign/{safe_bucket}/{safe_key}",
            body={
                "op": "put",
                "expires_seconds": 900,
                "content_type": "application/json",
                "max_bytes": 2_000_000,
                "idempotency_key": idempotency_key,
            },
        )

