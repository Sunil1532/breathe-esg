# MODEL.md — Breathe ESG Data Model

## Overview

Four concerns drive every field: **multi-tenancy**, **source-of-truth tracking**, **GHG Protocol classification**, and **immutable audit trail**.

---

## Entity diagram (simplified)

```
Organization
    │
    ├── OrganizationMembership ──── User
    │
    ├── IngestionJob
    │       │
    │       └── EmissionRecord (many) ──── AuditLog (many)
    │
    └── AuditLog (for org-level queries)
```

---

## Core invariants

1. **`EmissionRecord.raw_data` is immutable.** The full source row is stored as JSON on creation and never modified. If an analyst edits a quantity, the edit goes to `edit_history` and the raw original is untouched.
2. **`quantity_co2e_kg` may be null.** If emission factor lookup fails, the record is still created (flagged) rather than silently dropped. Analysts see it and can decide.
3. **`AuditLog` is append-only.** Django's `auto_now_add=True` + no update endpoint ensures every action is permanent.

---

## Multi-tenancy design

Row-level FK filtering: `EmissionRecord.objects.filter(organization=request.user.membership.organization)`. Every query is scoped at the view layer. Simpler than schema-per-tenant for a prototype; trade-off documented in TRADEOFFS.md.

---

## Unit normalization flow

```
Raw file value (any unit)
        │
        ▼
Parser: convert to canonical unit
  Fuel:         → Litres (L)
  Gas:          → Cubic metres (M3)
  Electricity:  → Kilowatt-hours (KWH)
  Air travel:   → passenger-kilometres (haversine × 1.08 detour × cabin multiplier)
  Hotel:        → room-nights
  Car/Rail:     → kilometres
        │
        ▼
quantity_normalized + normalized_unit
        │
        × emission_factor (kg CO₂e per normalized_unit)
        │
        ▼
quantity_co2e_kg
```

---

## Emission factors used

All sourced from DEFRA 2023 Greenhouse Gas Reporting Factors:

| Fuel | Factor | Unit |
|---|---|---|
| Diesel | 2.68 | kg CO₂e/L |
| Natural gas | 2.02 | kg CO₂e/M3 |
| Petrol | 2.31 | kg CO₂e/L |
| LPG | 1.51 | kg CO₂e/L |
| HFO | 3.35 | kg CO₂e/L |

| Region | Grid factor | Source |
|---|---|---|
| Germany | 0.434 | DEFRA 2023 |
| UK | 0.233 | DEFRA 2023 |
| USA | 0.386 | EPA eGRID 2022 |
| India | 0.820 | CEA 2022 |
| France | 0.052 | RTE 2022 |

| Travel mode | Factor | Unit |
|---|---|---|
| Air economy short (<3700 km) | 0.255 | kg CO₂e/pax-km |
| Air economy long (≥3700 km) | 0.195 | kg CO₂e/pax-km |
| Air business long | 0.429 | kg CO₂e/pax-km |
| Hotel | 31.7 | kg CO₂e/room-night |
| Car (average) | 0.168 | kg CO₂e/km |
| Rail (national) | 0.041 | kg CO₂e/km |

Air factors include Radiative Forcing Index (RFI) multiplier of 1.9 per DEFRA 2023.

---

## Status state machine

```
              ┌─────────────┐
              │   PENDING   │ ◄─── created by parser
              └──────┬──────┘
                     │  (analyst action or auto-flag)
             ┌───────┴───────┐
             ▼               ▼
        ┌─────────┐     ┌──────────┐
        │ FLAGGED │     │ (direct) │
        └────┬────┘     └────┬─────┘
             │               │
        ┌────▼───────────────▼────┐
        │                         │
    ┌───▼────┐             ┌──────▼──┐
    │APPROVED│             │REJECTED │
    └────────┘             └─────────┘
    (terminal)             (terminal)
```

FLAGGED is non-terminal: a flagged record can be approved after analyst review.
