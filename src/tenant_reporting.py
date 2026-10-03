from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DonorReceiptModel:
    sender_name: str
    reply_to: str
    annual_summary: bool = True


@dataclass(frozen=True)
class VolunteerReminderModel:
    sender_name: str
    hours_before_shift: int


@dataclass(frozen=True)
class CampaignReportingModel:
    campaign_id: str
    cadence: Literal["daily", "weekly", "monthly"]


@dataclass(frozen=True)
class TenantProvisionRequest:
    nonprofit_name: str
    tenant_slug: str
    website_target: str
    receipts: DonorReceiptModel
    reminders: VolunteerReminderModel
    reporting: CampaignReportingModel


@dataclass(frozen=True)
class TenantPlan:
    hostname: str
    record_name: str
    record_content: str
    record_id: str
    report_object_key: str
    upload_idempotency_key: str


def build_tenant_plan(request: TenantProvisionRequest, root_domain: str) -> TenantPlan:
    domain = root_domain.strip().lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
        raise ValueError("ROOT_DOMAIN must be a DNS domain")
    slug = request.tenant_slug.lower()
    campaign = request.reporting.campaign_id.lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", slug):
        raise ValueError("tenant_slug must be a DNS-safe label")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", campaign):
        raise ValueError("campaign_id must be path-safe")
    if request.reminders.hours_before_shift not in range(1, 169):
        raise ValueError("hours_before_shift must be between 1 and 168")
    return TenantPlan(
        hostname=f"{slug}.{domain}",
        record_name=slug,
        record_content=request.website_target,
        record_id=f"tenant-{slug}-cname",
        report_object_key=f"campaigns/{slug}/{campaign}/summary.json",
        upload_idempotency_key=f"report-{slug}-{campaign}",
    )

