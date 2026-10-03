from __future__ import annotations

import os
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .infrai_client import InfraiClient, InfraiError
from .tenant_reporting import TenantProvisionRequest, build_tenant_plan


class TenantProvisionResponse(BaseModel):
    tenant_hostname: str
    dns_record_type: Literal["CNAME"]
    report_object_key: str
    report_upload_url: str
    reporting_cadence: Literal["daily", "weekly", "monthly"]


def create_app(client: InfraiClient | None = None) -> FastAPI:
    root_domain = os.environ.get("ROOT_DOMAIN", "nonprofits.example.org")
    bucket = os.environ.get("INFRAI_ASSET_BUCKET", "nonprofit-tenant-assets")
    api_key = os.environ.get("INFRAI_API_KEY")
    infrai = client or InfraiClient(api_key=api_key or "")
    app = FastAPI(title="Nonprofit tenant provisioner")

    @app.on_event("startup")
    def ensure_asset_bucket() -> None:
        if client is None and not api_key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        try:
            infrai.create_bucket(bucket)
        except InfraiError as error:
            if error.status_code != 409:
                raise

    @app.post("/tenants", response_model=TenantProvisionResponse, status_code=201)
    def provision_tenant(request: TenantProvisionRequest) -> TenantProvisionResponse:
        plan = build_tenant_plan(request, root_domain)
        try:
            domain = infrai.get_domain(root_domain)
            zone_id = str(domain["zone_id"])
            infrai.upsert_record(
                zone_id=zone_id,
                name=plan.record_name,
                content=plan.record_content,
                record_id=plan.record_id,
            )
            signed = infrai.presign_upload(
                bucket=bucket,
                key=plan.report_object_key,
                idempotency_key=plan.upload_idempotency_key,
            )
        except InfraiError as error:
            client_status = error.status_code if 400 <= error.status_code < 500 else 502
            raise HTTPException(
                status_code=client_status,
                detail={"code": error.code, "message": str(error.detail.get("message", error.code))},
            ) from error

        return TenantProvisionResponse(
            tenant_hostname=plan.hostname,
            dns_record_type="CNAME",
            report_object_key=plan.report_object_key,
            report_upload_url=str(signed["url"]),
            reporting_cadence=request.reporting.cadence,
        )

    return app


app = create_app()
