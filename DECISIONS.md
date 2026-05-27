# DECISIONS.md — Ambiguity Log

Every significant design decision made during this build, with rationale and what I'd ask the PM.

---

## SAP: Which export mechanism?

**Options researched**: IDoc (EDI-style XML), OData (REST), BAPI (RFC call), flat file (SE16/MB51 export).

**Chose**: Flat file, semicolon-delimited, MB51 format.

**Why**: MB51 is the Material Document List — the standard transaction for viewing goods movements in SAP MM. It's what a sustainability lead would extract manually: run MB51 with movement types 261/201, export via "Spreadsheet" button. The result is a semicolon-delimited file with German column headers (MANDT, BUKRS, WERKS, MATNR, etc.) because that's the SAP default locale. German decimal format (1.234,56) and YYYYMMDD dates are realistic.

IDoc and OData are more robust for production but require IT involvement and SAP middleware configuration. A facilities lead doing a one-time export isn't calling a BAPI.

**Movement type filtering**: We only process consumption movements (261 = goods issue to cost center, 201 = goods issue to order, 281/551 = similar). We explicitly skip 101 (goods receipt) because receipts are procurement, not consumption — they'd double-count if included alongside a later 261.

**What I'd ask the PM**: Are clients on SAP S/4HANA or ECC? S/4HANA has a better OData API (C_MaterialDocItm_1), and if this is production we should build that instead. Also: what SAP modules are licensed? Not all clients have MM.

---

## SAP: Material-to-fuel mapping

**Problem**: SAP material numbers (MATNR) are client-specific — "MAT-10045" at one company might be diesel, at another it's solvent. There's no universal mapping.

**Chose**: A configurable lookup dict keyed on MAKTX (material description text), with partial string matching. We map German and English descriptions like "Diesel", "Dieselkraftstoff", "Erdgas", "Benzin".

**Trade-off**: This will miss client-specific descriptions ("KS-95", "FUELS-A"). In production, we'd need an onboarding step where the client maps their MATNR list to fuel types. Unknown materials are flagged, not dropped, so analysts can catch them.

**What I'd ask the PM**: Does Breathe have an onboarding playbook for material mapping? Is there a standard taxonomy clients are expected to provide?

---

## Utility: Which ingestion mode?

**Options**: PDF bill parsing (messy), portal CSV export (structured), direct utility API (Green Button / ESPI standard).

**Chose**: Portal CSV export.

**Why**: Green Button is theoretically standard but adoption is inconsistent — many UK and EU utilities don't implement it. PDF parsing is fragile and requires OCR. The CSV export from a utility portal (like E.ON, RWE, or SSE's online portals) is realistic: facilities managers already do this monthly. It's the middle ground between full automation (direct API) and ad-hoc (PDF OCR).

**Format assumptions**: Meter ID, site name, billing period start/end, consumption in kWh, optional peak demand and tariff code. We handle billing periods that don't align to calendar months by using the period_start/period_end fields as-is rather than forcing month normalization.

**What I'd ask the PM**: Which utilities are the client's providers? E.ON, Vattenfall, RWE have different export formats. Also: does the client have interval (15-min) data or just billing period totals? Interval data enables more accurate reporting.

---

## Travel: Concur vs Navan vs expense report

**Chose**: Concur-style segment CSV.

**Why**: Concur is market-leading for enterprise travel management (>60% enterprise market share per Phocuswire 2022). The export format has a segment-per-row structure with fields like SegmentType, Origin, Destination, TravelDate, CabinClass, TotalCost, Currency. Navan uses a similar structure. This is realistic for an enterprise client onboarding.

**Distance calculation**: When airport codes are provided but no distance, we use haversine formula between airport coordinates (65 major airports hardcoded, extensible) × 1.08 detour factor (per DEFRA methodology for scheduled vs direct routing). Short haul threshold: 3,700 km (DEFRA 2023 cutoff).

**Cabin class emission factors**: Economy short/long and business long are differentiated per DEFRA 2023. Premium economy is treated as business for conservatism. First class would need a separate factor but isn't in the sample data.

**What I'd ask the PM**: Does the client have Concur? Or are they using Navan, TravelPerk, or something else? And do they want flight emissions including or excluding RFI? (We include RFI=1.9 per DEFRA, which is the more conservative choice.)

---

## Frontend: Served from Django vs separate deployment

**Chose**: Build React to `backend/staticfiles/frontend/` and serve via Django + WhiteNoise.

**Why**: Simpler to deploy (one Render service, not two). WhiteNoise handles compression and caching headers. The catch-all URL pattern in `urls.py` serves the React `index.html` for all non-API routes, enabling client-side routing.

**Trade-off**: A separate React deployment on Vercel/Netlify would give CDN edge serving and instant cache invalidation. For this prototype, the simplicity win outweighs the performance difference.

---

## Auth: JWT vs session

**Chose**: JWT (SimpleJWT), 8-hour access token, 7-day refresh with rotation.

**Why**: DRF + JWT is a clean stateless API that the React frontend can consume without CSRF complications. Session auth requires same-origin or careful CSRF configuration.

**8-hour access token**: Long enough for a full analyst workday without re-login. Short enough that a stolen token expires the same day. The 7-day refresh with rotation means re-login is required weekly.

---

## Database: SQLite vs PostgreSQL

**Chose**: SQLite for local dev, PostgreSQL for production (via `DATABASE_URL` env var).

**Why**: SQLite requires zero setup for local development. `dj_database_url` makes switching to Postgres a one-line env var change. Render provides a managed Postgres add-on.

**SQLite limits**: No concurrent writes, no row-level locking. Fine for a prototype, not for production with multiple analysts simultaneously approving records.

---

## What I explicitly did NOT research / scope out

Documented in TRADEOFFS.md.
