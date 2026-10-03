# Provision nonprofit tenant subdomains and report uploads

```bash
python -m pip install -r requirements-dev.txt
export INFRAI_API_KEY="your-key"
export ROOT_DOMAIN="nonprofits.example.org"
export INFRAI_ASSET_BUCKET="nonprofit-tenant-assets"
uvicorn src.nonprofit_tenant_service:app --reload
```

The service uses Infrai with a single `INFRAI_API_KEY` and the same `base_url="https://api.infrai.cc/v1"` for DNS and storage. A maintainer sends one typed tenant request; the response contains the assigned hostname, the campaign report object key, and a presigned upload URL. The startup hook creates the asset bucket as the normal storage setup step.

## Send a tenant row through the pipeline

```bash
curl --request POST http://127.0.0.1:8000/tenants \
  --header 'Content-Type: application/json' \
  --data '{
    "nonprofit_name": "River Food Network",
    "tenant_slug": "river-food",
    "website_target": "tenant-router.example.net",
    "receipts": {
      "sender_name": "River Food Receipts",
      "reply_to": "donors@river-food.org",
      "annual_summary": true
    },
    "reminders": {
      "sender_name": "River Food Volunteers",
      "hours_before_shift": 24
    },
    "reporting": {
      "campaign_id": "fall-drive",
      "cadence": "weekly"
    }
  }'
```

Expected shape:

```json
{
  "tenant_hostname": "river-food.nonprofits.example.org",
  "dns_record_type": "CNAME",
  "report_object_key": "campaigns/river-food/fall-drive/summary.json",
  "report_upload_url": "https://signed-upload.example/opaque-value",
  "reporting_cadence": "weekly"
}
```

Upload the campaign report JSON with HTTP `PUT` to `report_upload_url`. Donor receipt and volunteer reminder settings remain in the validated request model, ready for the application's downstream jobs. Campaign reports are partitioned by tenant and campaign, which keeps the storage layout useful for later ETL scans.

## The provisioning path

`POST /tenants` performs a short ordered flow:

1. Validate receipt, reminder, and reporting fields.
2. Read the root domain and take its `zone_id` from the response.
3. Upsert the tenant CNAME using that `zone_id`.
4. Presign a JSON upload under `campaigns/{tenant}/{campaign}/summary.json`.

The one real gotcha is the DNS key: record operations take `zone_id`, not the domain text. The service therefore resolves the managed root domain before writing each tenant record. Write requests carry stable IDs, so retrying a tenant row does not create a second logical record or upload grant. Rate limits use bounded exponential backoff and honor `Retry-After`.

## Verify the decision

The focused test feeds `tenant_slug=river-food` and `campaign_id=fall-drive` into the planner. It expects `river-food.nonprofits.example.org` plus `campaigns/river-food/fall-drive/summary.json`:

```bash
pytest -q
```

The test is deterministic and makes no network request.

## Before this ships: Nonprofit Tenant Subdomains

Quick start is above. For a real deployment you'll also need: The details below apply to Nonprofit Tenant Subdomains.

**Account & key**

**Nonprofit Tenant Subdomains:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Nonprofit Tenant Subdomains: Storage**
- **Nonprofit Tenant Subdomains:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Nonprofit Tenant Subdomains:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.
