from src.tenant_reporting import (
    CampaignReportingModel,
    DonorReceiptModel,
    TenantProvisionRequest,
    VolunteerReminderModel,
    build_tenant_plan,
)


def test_campaign_report_is_namespaced_under_the_nonprofit_tenant() -> None:
    request = TenantProvisionRequest(
        nonprofit_name="River Food Network",
        tenant_slug="river-food",
        website_target="tenant-router.example.net",
        receipts=DonorReceiptModel(
            sender_name="River Food Receipts",
            reply_to="donors@river-food.org",
            annual_summary=True,
        ),
        reminders=VolunteerReminderModel(
            sender_name="River Food Volunteers",
            hours_before_shift=24,
        ),
        reporting=CampaignReportingModel(campaign_id="fall-drive", cadence="weekly"),
    )

    plan = build_tenant_plan(request, "nonprofits.example.org")

    assert plan.hostname == "river-food.nonprofits.example.org"
    assert plan.record_name == "river-food"
    assert plan.record_content == "tenant-router.example.net"
    assert plan.report_object_key == "campaigns/river-food/fall-drive/summary.json"
    assert plan.upload_idempotency_key == "report-river-food-fall-drive"
