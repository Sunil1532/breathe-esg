# SOURCES.md — Source Format Research

For each of the three ingestion sources: what I researched, what I found, how the sample data reflects it, and what would break in production.

---

## Source 1: SAP Fuel & Procurement

### What I researched

SAP MM (Materials Management) movement data. Key SAP transactions:
- **MB51** — Material Document List. The standard report for goods movements. Used by logistics and finance to reconcile inventory. A sustainability lead would run MB51 with movement type filter and export via the "Spreadsheet" button.
- **SE16** — Table browser. Used by IT/consultants to pull raw MARA/MSEG data.
- **MB52** — Warehouse stocks. Less relevant (stock levels vs movements).

SAP export formats: The "Spreadsheet" export from MB51 produces a tab-delimited or semicolon-delimited flat file. Column headers are in the **system language** of the SAP instance — German headers for German installations, which is the most common enterprise configuration in Europe.

Key fields in MSEG (material document segment table):
- `MANDT` — Client (always a 3-digit number, e.g. "100")
- `BUKRS` — Company code (e.g. "DE01")
- `WERKS` — Plant (4-char, e.g. "DE01" for Hamburg plant)
- `MATNR` — Material number (18-char, often padded with leading zeros)
- `MAKTX` — Material description text (from MARA/MAKT tables)
- `BLDAT` — Document date (YYYYMMDD)
- `BUDAT` — Posting date (YYYYMMDD)
- `MENGE` — Quantity (decimal, German format: comma as decimal separator, period as thousands separator)
- `MEINS` — Base unit of measure (SAP unit code: "L" for litres, "M3" for cubic metres, "KG" for kilograms, "ST" for pieces)
- `BWART` — Movement type (3-digit: "261" = goods issue to cost center, "101" = goods receipt)
- `KOSTL` — Cost center

**Movement types that indicate consumption** (and should be ingested):
- 261: Goods issue to cost center (most common for fuel)
- 201: Goods issue to order
- 281: Goods issue from project stock
- 551: Scrapping

**Movement types to exclude**:
- 101: Goods receipt (procurement, not consumption — including this double-counts)
- 102, 122: Reversals
- 301–309: Stock transfers (no net consumption)

### What the sample data looks like

`sap_fuel_procurement.csv` is a semicolon-delimited file with:
- German column headers (MANDT;BUKRS;WERKS;MATNR;MAKTX;BLDAT;MENGE;MEINS;BWART;KOSTL)
- Dates as YYYYMMDD strings ("20240115")
- Quantities in German decimal format ("1.234,56" = 1234.56)
- Mixed units: L (diesel, petrol), M3 (natural gas), KG (HFO)
- Three plants: DE01 (Hamburg), DE02 (Berlin), DE03 (Munich)
- One row with movement type 101 (should be filtered out by parser)
- One row with unknown material "Schmierstoffe" (lubricants — triggers UNKNOWN_MATERIAL flag)
- HFO (heavy fuel oil) entries at DE03 for a boiler

### What would break in production

1. **Material number mapping**: Our material-to-fuel-type lookup uses MAKTX (text description). Client descriptions vary: "DK" for diesel, "NG" for natural gas, custom internal codes. Would need an onboarding step where the client provides a material mapping spreadsheet.

2. **Units beyond our lookup table**: SAP has hundreds of unit codes. We handle L, KG, M3, KWH, ST, PAL, TO. Client may have "GAL" (gallons), "BBL" (barrels), or custom units. Would need a more comprehensive conversion table.

3. **Company code / plant hierarchy**: We store `WERKS` as `facility_code` but don't currently resolve plant → building → country. In production, you'd want a plant master that maps plant codes to facility names, addresses, and country codes (for correct grid factor selection on co-generation plants).

4. **Multi-client SAP**: Large enterprises have multiple SAP instances or clients. A single file might have records for DE01, US01, and GB01 plants, which should use different emission factors. We use `Organization.country_code` as a global default rather than per-plant.

5. **Delta exports**: MB51 is usually run for a period. If a finance user re-runs it after a correction, we'd see duplicate document numbers. The `source_system_id` field (set to the SAP document number + line item) supports deduplication but the upsert logic isn't fully implemented.

---

## Source 2: Utility Electricity

### What I researched

How facilities teams get electricity consumption data:

- **Green Button** (US): A data standard (ESPI — Energy Services Provider Interface) that many US utilities implement. Provides XML or JSON interval data via a REST API. Well-structured but adoption is still inconsistent, especially at smaller utilities.
- **Utility portal CSV exports** (UK/EU): Online portals (E.ON myAccount, EDF Energy, Scottish Power, RWE, Vattenfall) all offer CSV downloads of billing data. The format varies but typically includes meter ID, billing period, consumption in kWh, and tariff.
- **PDF bills**: Most common but hardest to parse. Would require OCR + table extraction.

**Billing period misalignment**: Utility billing cycles rarely align to calendar months. A bill period might be 2024-01-15 to 2024-02-12. Our model stores `period_start` and `period_end` as-is rather than forcing month normalization — this preserves the source data and lets analysts handle period allocation when producing monthly reports.

**Meter IDs**: Each physical meter has a MPAN (UK) or meter serial number. Sites may have multiple meters (main supply, sub-meters by floor/department). We store meter ID as `facility_code` and `source_system_id`.

### What the sample data looks like

`utility_electricity.csv` has columns: `meter_id, site_name, period_start, period_end, consumption_kwh, peak_demand_kw, tariff_code, unit_rate_pence_per_kwh, standing_charge_pence_per_day, currency`

Features:
- Three meters across two sites (Hamburg HQ, Berlin office)
- Billing periods that span ~45 days, not calendar months
- One meter with a mid-period read (billing period splits — realistic for meter exchanges)
- Missing `peak_demand_kw` for one row (non-fatal warning)
- One row with negative consumption (meter reversal or data entry error — triggers NON_POSITIVE_USAGE flag)
- EUR currency

### What would break in production

1. **Half-hourly interval data**: Large industrial sites have smart meters with 30-minute interval data. Our parser handles billing period totals only. Interval data would need aggregation to billing periods before ingestion, or a separate higher-resolution data model.

2. **Reactive power / power factor**: Some bills include reactive energy (kVArh) charges. We ignore these as they don't have CO₂e factors under standard methodology.

3. **Heat and steam**: The model assumes electricity-only for Scope 2. District heating and steam purchases are also Scope 2 but have different emission factors. Would need a `utility_type` field and separate factor lookup.

4. **Renewable certificates**: If the client has PPAs (Power Purchase Agreements) or REGOs/GOs, market-based emission factors can be zero. We don't model this — see TRADEOFFS.md.

5. **Multi-currency utility bills**: Our sample uses EUR. USD, GBP, and mixed-currency portfolios are common for multinational clients. We store the raw unit rate and currency but don't do currency conversion for spend data.

---

## Source 3: Corporate Travel

### What I researched

Corporate travel expense management platforms:
- **Concur Travel & Expense** (SAP): Market leader, >60% enterprise share. Exports a "Segment Detail" CSV via their Analytics product. Each row is one travel segment (flight leg, hotel night, car rental day, rail journey).
- **Navan (formerly TripActions)**: Similar segment-level export. JSON API available.
- **TravelPerk**: REST API with similar segment structure.
- **Egencia (Amex GBT)**: Similar CSV export.

**Key insight**: Travel expense systems give you airport codes (IATA, e.g. "LHR", "FRA"), not distances. Distance calculation is the app's responsibility.

**Distance calculation methodology** (per DEFRA 2023):
- Use great-circle distance (haversine formula) between origin and destination airport coordinates
- Multiply by 1.08 (8% detour factor to account for actual flight routing vs straight line)
- For short haul (<3,700 km) vs long haul (≥3,700 km), use different emission factors (DEFRA methodology splits at this threshold)

**Cabin class factors** (DEFRA 2023, includes RFI=1.9):
- Economy short haul: 0.255 kg CO₂e/pax-km
- Economy long haul: 0.195 kg CO₂e/pax-km  
- Business long haul: 0.429 kg CO₂e/pax-km
- First class: ~0.599 kg CO₂e/pax-km (not in sample, would need addition)

**Note on RFI (Radiative Forcing Index)**: Aviation emissions have a warming effect beyond CO₂ from contrails and NOx at altitude. DEFRA 2023 applies a multiplier of 1.9 to reflect this. Some clients prefer to report without RFI (simpler, just CO₂). We include RFI as it's the more defensible choice.

### What the sample data looks like

`travel_concur.csv` has columns: `trip_id, traveler_name, segment_type, origin_code, destination_code, travel_date, return_date, cabin_class, distance_km, hotel_name, room_nights, currency, total_cost`

Features:
- 16 trips, mix of segment types: AIR, HOTEL, CAR, RAIL, FERRY
- FERRY segments are skipped (no emission factor — documented as warning)
- Mix of short-haul (FRA-LHR) and long-haul (FRA-JFK, FRA-SIN) flights
- Business class and economy entries
- Unknown airport codes ("UNKNOWN_CODE") — triggers UNKNOWN_AIRPORT flag
- Hotel stays with room_nights field
- Car rentals with distance_km
- EUR and GBP currency entries
- Round trips (separate outbound/return rows, realistic for Concur)

### What would break in production

1. **Airport code completeness**: Our lookup table has ~65 major airports. Clients flying to regional airports (e.g. Aberdeen ABZ, Exeter EXT, Cologne CGN) would get UNKNOWN_AIRPORT flags. Would need a full IATA database (10,000+ airports) with coordinates. OpenFlights.org provides this as a CSV under CC-BY.

2. **Hotel emission factors**: Our 31.7 kg CO₂e/room-night is a global average (DEFRA 2023). This varies enormously by country (a UK hotel vs a US hotel vs an Indian hotel). A proper implementation would use country-specific hotel factors.

3. **Concur API pagination**: The CSV export approach breaks down for companies with >100,000 annual trips. The Concur Analytics API paginates at 500 rows. Would need to handle pagination and incremental syncs.

4. **Per-person vs total cost**: Concur reports can have a "group booking" where one row covers multiple travelers. We assume one row = one traveler, which would undercount emissions for group bookings. The `traveler_name` field could be extended to a `traveler_count` field.

5. **Taxi / rideshare**: Uber, Lyft, and local taxi expenses often appear in travel reports. They have different emission factors (EV vs ICE) and we don't currently handle them.
