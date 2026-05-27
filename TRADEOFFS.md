# TRADEOFFS.md — Three Deliberate Non-Builds

The assignment asks for three things deliberately not built, with explanation. Here are five (three required, two bonus), ordered by impact.

---

## 1. Scope 2 dual reporting (location-based vs market-based)

**What it is**: The GHG Protocol requires companies to report Scope 2 emissions using two methods: location-based (grid average emission factor for the region) and market-based (supplier-specific or contractual factor, e.g. from a renewable energy certificate).

**Why I didn't build it**: This requires parallel calculation pipelines, separate UI presentation, and a market-based factor data source (which usually comes from energy attribute certificate registries like REGO in the UK or GO in Europe). The data model has a `custom_grid_factor_kg_per_kwh` field on Organization that supports overriding the default grid factor — so a single market-based factor per org is possible. But the dual-reporting requirement means storing *both* results simultaneously, which doubles the complexity of every Scope 2 display, export, and audit output.

**What I'd need to build it**: Add `quantity_co2e_kg_location_based` and `quantity_co2e_kg_market_based` columns to `EmissionRecord`. Update all dashboard aggregations to handle both. Add UI toggles. The data model comment (`# Allows overriding the default grid factor`) is intentional — it signals where to hook in.

---

## 2. Schema-per-tenant isolation

**What it is**: Instead of filtering all queries by `organization_id`, use a separate PostgreSQL schema (or database) per client. Cross-tenant data leakage becomes structurally impossible rather than defensively prevented.

**Why I didn't build it**: Django's multi-tenant support (`django-tenants`) adds significant complexity to migrations, management commands, and every query. For a 4-day prototype with one test org, it's disproportionate overhead. The current row-level approach with FK filtering in every viewset is correct for a prototype, and the `get_user_org` helper is consistently used in every view so the risk of a cross-org query is low.

**When it matters**: As soon as a second client is onboarded, schema-per-tenant is worth the investment. A misconfigured view in the current model could expose one client's data to another. For production, I'd migrate to `django-tenants` or use PostgreSQL's Row Level Security.

---

## 3. Export / audit report generation

**What it is**: Producing a formatted output (PDF, XLSX, or structured JSON) of approved records for submission to an external auditor or for upload to a GHG registry.

**Why I didn't build it**: The review → approve workflow is complete. But the final step — generating a defensible audit package — is a product feature, not just an API endpoint. It requires knowing: what format the auditor expects, whether to include the full `raw_data` chain, which emission factor sources to cite, whether to include `AuditLog` entries per record or as a separate attachment. These are PM questions, not engineering ones.

**What I'd need to build it**: A backend task (Celery or a simple management command) that filters `EmissionRecord.objects.filter(status='APPROVED')`, aggregates by scope/category/period, and renders to XLSX using `openpyxl`. Add a download button to the dashboard. 2–3 days of work once the format is specified.

---

## Bonus 1: Real-time duplicate detection across uploads

**What it is**: If an analyst uploads January's utility CSV, then re-uploads it with one corrected row, the system currently creates duplicate records for the unchanged rows. The `file_hash` check prevents exact-duplicate files but not partial overlaps.

**Trade-off**: Implemented `source_system_id` on `EmissionRecord` (document number, trip ID, meter ID + period). The upsert logic would use this as the idempotency key. Skipped because it requires a merge strategy (overwrite vs create-and-flag the old) that has business implications.

---

## Bonus 2: Automated emission factor updates

**What it is**: DEFRA publishes updated factors annually. The current system has factors hardcoded in `emission_factors.py`. When factors change, historical records need to be recomputed — but only if the client wants restated figures, not overwritten ones (a compliance decision).

**Trade-off**: The `emission_factor` and `emission_factor_source` fields on each record make this auditable when done. The recomputation logic is a simple bulk update. What I didn't build is the update mechanism, the versioning of factor sets, and the UI prompt asking "DEFRA 2024 factors are available — restate your 2023 records?" This is a significant product feature with compliance implications.
