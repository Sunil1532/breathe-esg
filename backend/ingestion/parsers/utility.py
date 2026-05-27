"""
Utility electricity data parser.

Format chosen: Portal CSV export (e.g. utility web portal download).

Why this over PDF bills or API?
- PDF bills require OCR, are highly vendor-specific, and are the hardest format
  to parse reliably. Acceptable for a later phase.
- Most utility portals (PG&E, Con Ed, E.ON, EnBW, etc.) offer a CSV download
  of interval or billing data. This is the format facilities teams actually use
  when they "pull data from the portal" — it's the path of least resistance.
- Green Button Data (XML) is an official US standard but adoption is spotty
  outside of California; CSV is more universal.

Real-world quirks handled:
- Usage in kWh or MWh (normalize to kWh)
- Billing periods that span month boundaries (split is out of scope — we use
  the full billing period as the record period)
- Missing peak demand (common for smaller meters)
- Meters that appear mid-period (new facility onboarding)
- Currency as string (USD, EUR, GBP — stored for reference, not used in CO2e)
- Multiple meters per account

What we deliberately do not handle:
- Gas, water, or heat meters — those would fall under Scope 1 or custom Scope 2.
  This prototype is electricity-only; flag if meter_type != Electricity.
- Time-of-use interval data (15-min reads) — aggregate to billing period.
- Multi-fuel utility bills.
"""

import io
import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

from ingestion.emission_factors import GRID_FACTORS, get_grid_factor


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d.%m.%Y', '%Y%m%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def _parse_decimal(raw: str) -> Decimal:
    raw = raw.strip().replace(',', '')
    if not raw:
        raise ValueError("Empty number")
    return Decimal(raw)


def _normalize_to_kwh(quantity: float, unit: str) -> tuple[float, str]:
    """Convert usage to kWh."""
    unit_upper = unit.strip().upper().replace(' ', '')
    if unit_upper in ('KWH', 'KW-H', 'KILOWATT-HOUR', 'KILOWATTHOUR'):
        return quantity, 'kWh'
    if unit_upper in ('MWH', 'MW-H', 'MEGAWATT-HOUR', 'MEGAWATTHOUR'):
        return quantity * 1000.0, 'kWh'
    if unit_upper in ('GWH', 'GIGAWATT-HOUR'):
        return quantity * 1_000_000.0, 'kWh'
    if unit_upper in ('GJ', 'GIGAJOULE'):
        return quantity * 277.778, 'kWh'  # 1 GJ = 277.778 kWh
    # Unknown unit — return as-is, flag it
    return quantity, unit


# Canonical column names (flexible header detection)
HEADER_ALIASES = {
    'account number': 'account_number',
    'account_number': 'account_number',
    'account': 'account_number',
    'meter id': 'meter_id',
    'meter_id': 'meter_id',
    'meter': 'meter_id',
    'service address': 'address',
    'service_address': 'address',
    'address': 'address',
    'billing period start': 'period_start',
    'period_start': 'period_start',
    'start date': 'period_start',
    'billing period end': 'period_end',
    'period_end': 'period_end',
    'end date': 'period_end',
    'usage (kwh)': 'usage_kwh',
    'usage_kwh': 'usage_kwh',
    'usage': 'usage_kwh',
    'consumption': 'usage_kwh',
    'energy (kwh)': 'usage_kwh',
    'peak demand (kw)': 'peak_demand_kw',
    'peak_demand_kw': 'peak_demand_kw',
    'peak demand': 'peak_demand_kw',
    'rate schedule': 'rate_schedule',
    'rate_schedule': 'rate_schedule',
    'tariff': 'rate_schedule',
    'cost (usd)': 'cost',
    'cost': 'cost',
    'amount': 'cost',
    'currency': 'currency',
    'meter type': 'meter_type',
    'meter_type': 'meter_type',
    'type': 'meter_type',
    'unit': 'usage_unit',
    'usage unit': 'usage_unit',
}


def _map_headers(raw_headers: list[str]) -> dict[str, int]:
    result = {}
    for i, h in enumerate(raw_headers):
        canonical = HEADER_ALIASES.get(h.strip().lower())
        if canonical:
            result[canonical] = i
    return result


def parse_utility_csv(file_content: bytes, country_code: str = 'DE',
                      custom_grid_factor: float = None) -> Iterator[dict]:
    """
    Yields parsed utility row dicts.
    country_code is used to select the location-based grid emission factor.
    custom_grid_factor overrides the country default (market-based accounting).
    """
    text = file_content.decode('utf-8', errors='replace')
    reader = csv.reader(io.StringIO(text))

    headers = None
    col_map = {}

    grid_factor, grid_source = get_grid_factor(country_code, custom_grid_factor)

    for row_num, row in enumerate(reader, start=1):
        while row and row[-1] == '':
            row.pop()
        if not row:
            continue

        if headers is None:
            headers = row
            col_map = _map_headers(headers)
            if 'usage_kwh' not in col_map:
                yield {'error': f"Row {row_num}: Cannot find usage column. "
                               f"Expected 'Usage (kWh)', 'Usage', or 'Consumption'. "
                               f"Found headers: {headers}"}
                return
            continue

        def get(field: str, default='') -> str:
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        # Meter type check
        meter_type = get('meter_type', 'Electricity')
        flags = []
        warnings = []

        if meter_type and meter_type.lower() not in (
            'electricity', 'electric', 'power', '', 'kwh', 'elec'
        ):
            flags.append({
                'code': 'NON_ELECTRICITY_METER',
                'message': f"Meter type is {meter_type!r}. This parser handles electricity only. "
                           f"CO2e calculated but Scope 2 classification may be wrong.",
            })

        # Parse usage
        usage_raw = get('usage_kwh', '')
        try:
            raw_qty = _parse_decimal(usage_raw)
        except (ValueError, InvalidOperation):
            yield {'error': f"Row {row_num}: Cannot parse usage {usage_raw!r}",
                   'row': row_num, 'raw': dict(zip(headers, row))}
            continue

        if raw_qty <= 0:
            yield {'error': f"Row {row_num}: Non-positive usage {raw_qty}; skipped.",
                   'row': row_num}
            continue

        # Determine unit and normalize to kWh
        usage_unit = get('usage_unit', 'kWh') or 'kWh'
        norm_qty, norm_unit = _normalize_to_kwh(float(raw_qty), usage_unit)

        if norm_unit != 'kWh':
            flags.append({
                'code': 'UNKNOWN_UNIT',
                'message': f"Unknown unit {usage_unit!r}; stored as-is. "
                           f"CO2e cannot be calculated until unit is resolved.",
            })

        # Parse dates
        try:
            period_start = _parse_date(get('period_start', ''))
        except ValueError as e:
            yield {'error': f"Row {row_num}: Billing period start: {e}", 'row': row_num}
            continue

        try:
            period_end = _parse_date(get('period_end', ''))
        except ValueError:
            # Fall back: assume same-month end date
            period_end = period_start
            warnings.append({'code': 'MISSING_PERIOD_END',
                             'message': "Billing period end missing; using start date as end date."})

        if period_end < period_start:
            flags.append({'code': 'INVALID_PERIOD',
                          'message': f"Period end {period_end} is before period start {period_start}."})

        # CO2e calculation
        co2e_kg = None
        if norm_unit == 'kWh':
            co2e_kg = norm_qty * grid_factor

        # Flag very high single-period consumption (> 1 GWh in a billing period is unusual)
        if norm_qty > 1_000_000:
            flags.append({'code': 'LARGE_QUANTITY',
                          'message': f"Usage {norm_qty:,.0f} kWh exceeds 1 GWh — verify meter reading."})

        meter_id = get('meter_id', '')
        account = get('account_number', '')
        address = get('address', '')
        rate = get('rate_schedule', '')
        cost = get('cost', '')
        currency = get('currency', 'USD')

        description = ' — '.join(filter(None, [meter_id, address, rate]))

        yield {
            'record': {
                'scope': '2',
                'category': 'Purchased Electricity',
                'subcategory': f"Grid ({country_code})" + (" — market-based" if custom_grid_factor else " — location-based"),
                'fuel_type': 'electricity',
                'raw_quantity': float(raw_qty),
                'raw_unit': usage_unit,
                'quantity_normalized': norm_qty,
                'normalized_unit': norm_unit,
                'quantity_co2e_kg': co2e_kg,
                'emission_factor': grid_factor,
                'emission_factor_source': grid_source,
                'period_start': period_start,
                'period_end': period_end,
                'source_system_id': meter_id or account,
                'facility_code': meter_id,
                'description': description,
                'flags': flags,
                'raw_data': {
                    **dict(zip(headers, row)),
                    '_cost': cost,
                    '_currency': currency,
                },
            },
            'warnings': warnings,
        }
