"""
Corporate travel parser — Concur/Navan-style segment CSV export.

Format chosen: CSV segment export from Concur Travel (SAP Concur).

Why Concur CSV over Navan API?
- Concur is the dominant enterprise travel management system. Their standard
  report export (Expense Report or Trip Report as CSV) is what sustainability
  leads actually download.
- Navan and TripActions have APIs, but many enterprises still use Concur
  and the API requires OAuth + corporate IT involvement.
- CSV export is realistic for the "facilities lead pulls data manually" scenario.
- Both platforms export roughly the same segment-level fields.

Segment types handled:
- Air: origin/destination airport codes → haversine distance → emission factor
       by cabin class and haul type. If distance is provided explicitly, use it.
- Hotel: nights × room-night emission factor
- Car: distance × car emission factor. If distance not provided, flag it.
- Rail: distance × rail emission factor.

What we do NOT handle (TRADEOFFS.md):
- Taxi/rideshare (distance usually missing)
- Ferry
- Currency conversion (cost stored as-is)
- Trip consolidation (a multi-leg itinerary is multiple rows; each row is
  a separate emission record)
"""

import io
import csv
from datetime import date, datetime
from decimal import Decimal
from typing import Iterator

from ingestion.emission_factors import (
    get_flight_distance_km, get_air_emission_factor,
    GROUND_TRAVEL_FACTORS, AIR_SHORTHAUL_KM
)

HEADER_ALIASES = {
    'trip id': 'trip_id',
    'trip_id': 'trip_id',
    'report id': 'trip_id',
    'employee id': 'employee_id',
    'employee_id': 'employee_id',
    'user id': 'employee_id',
    'segment type': 'segment_type',
    'segment_type': 'segment_type',
    'type': 'segment_type',
    'category': 'segment_type',
    'origin': 'origin',
    'from': 'origin',
    'departure city': 'origin',
    'destination': 'destination',
    'to': 'destination',
    'arrival city': 'destination',
    'departure date': 'departure_date',
    'departure_date': 'departure_date',
    'check-in date': 'departure_date',
    'return date': 'return_date',
    'return_date': 'return_date',
    'check-out date': 'return_date',
    'class of service': 'cabin_class',
    'cabin_class': 'cabin_class',
    'class': 'cabin_class',
    'service class': 'cabin_class',
    'distance (km)': 'distance_km',
    'distance_km': 'distance_km',
    'distance': 'distance_km',
    'cost (usd)': 'cost',
    'cost': 'cost',
    'amount': 'cost',
    'currency': 'currency',
    'vendor': 'vendor',
    'airline': 'vendor',
    'hotel': 'vendor',
    'car company': 'vendor',
    'nights': 'nights',
    'number of nights': 'nights',
}


def _map_headers(raw_headers: list[str]) -> dict[str, int]:
    result = {}
    for i, h in enumerate(raw_headers):
        canonical = HEADER_ALIASES.get(h.strip().lower())
        if canonical:
            result[canonical] = i
    return result


def _parse_date(raw: str) -> date | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d.%m.%Y', '%b %d, %Y', '%d-%b-%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(raw: str) -> float | None:
    raw = raw.strip().replace(',', '')
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _classify_cabin(raw: str) -> str:
    raw = (raw or '').lower().strip()
    if 'business' in raw or 'biz' in raw or 'c class' in raw:
        return 'business'
    if 'first' in raw or 'f class' in raw:
        return 'first'
    if 'premium' in raw or 'premium economy' in raw or 'w class' in raw:
        return 'premium'
    return 'economy'  # default


def parse_travel_csv(file_content: bytes) -> Iterator[dict]:
    text = file_content.decode('utf-8', errors='replace')
    reader = csv.reader(io.StringIO(text))

    headers = None
    col_map = {}

    for row_num, row in enumerate(reader, start=1):
        while row and row[-1] == '':
            row.pop()
        if not row:
            continue

        if headers is None:
            headers = row
            col_map = _map_headers(headers)
            if 'segment_type' not in col_map and 'trip_id' not in col_map:
                yield {'error': f"Row {row_num}: Cannot identify required columns. "
                               f"Expected 'Segment Type' or 'Trip ID'. Found: {headers}"}
                return
            continue

        def get(field: str, default='') -> str:
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        segment_type = get('segment_type', '').upper()
        trip_id = get('trip_id', f"ROW-{row_num}")
        employee_id = get('employee_id', '')
        vendor = get('vendor', '')
        cost = _parse_float(get('cost', ''))
        currency = get('currency', 'USD')
        departure_date = _parse_date(get('departure_date', ''))
        return_date = _parse_date(get('return_date', ''))

        # Use departure as period_start, return (or departure) as period_end
        period_start = departure_date or date.today()
        period_end = return_date or period_start

        raw_data = dict(zip(headers, row))
        flags = []
        warnings = []

        # ── Air segment ──────────────────────────────────────────────────
        if segment_type in ('AIR', 'FLIGHT', 'PLANE', 'FLY'):
            origin = get('origin', '').upper()
            destination = get('destination', '').upper()
            cabin_raw = get('cabin_class', 'Economy')
            cabin = _classify_cabin(cabin_raw)

            # Distance: use provided value, else calculate from airport codes
            provided_distance = _parse_float(get('distance_km', ''))
            if provided_distance and provided_distance > 0:
                distance_km = provided_distance
                dist_source = 'provided in source data'
            else:
                distance_km, dist_source = get_flight_distance_km(origin, destination)

            if distance_km is None:
                flags.append({
                    'code': 'MISSING_DISTANCE',
                    'message': f"Cannot calculate distance: airport codes {origin!r}→{destination!r} "
                               f"not in lookup table. CO2e will be null.",
                })
                co2e_kg = None
                ef = None
                ef_source = ''
                norm_qty = 0
                norm_unit = 'passenger-km'
            else:
                ef, ef_source = get_air_emission_factor(distance_km, cabin)
                co2e_kg = distance_km * ef
                norm_qty = distance_km
                norm_unit = 'passenger-km'
                haul = 'short-haul' if distance_km < AIR_SHORTHAUL_KM else 'long-haul'
                ef_source = f"{ef_source} ({haul}, {cabin}, dist: {dist_source})"

            if not origin or not destination:
                flags.append({'code': 'MISSING_AIRPORTS',
                              'message': "Origin or destination airport code is empty."})

            yield {
                'record': {
                    'scope': '3',
                    'category': 'Business Travel',
                    'subcategory': f"Air — {cabin.title()} class",
                    'fuel_type': f"air_{cabin}",
                    'raw_quantity': distance_km or 0,
                    'raw_unit': 'km',
                    'quantity_normalized': norm_qty,
                    'normalized_unit': norm_unit,
                    'quantity_co2e_kg': co2e_kg,
                    'emission_factor': ef,
                    'emission_factor_source': ef_source,
                    'period_start': period_start,
                    'period_end': period_end,
                    'source_system_id': trip_id,
                    'facility_code': employee_id,
                    'description': f"Air: {origin}→{destination} ({cabin}) — {vendor}",
                    'flags': flags,
                    'raw_data': {**raw_data, '_cost': cost, '_currency': currency},
                },
                'warnings': warnings,
            }

        # ── Hotel segment ────────────────────────────────────────────────
        elif segment_type in ('HOTEL', 'ACCOMMODATION', 'LODGING'):
            nights_raw = _parse_float(get('nights', ''))
            if nights_raw is None or nights_raw <= 0:
                # Calculate from dates
                if departure_date and return_date and return_date > departure_date:
                    nights = (return_date - departure_date).days
                    warnings.append({'code': 'NIGHTS_CALCULATED',
                                    'message': f"Nights not provided; calculated from dates: {nights}"})
                else:
                    nights = 1
                    flags.append({'code': 'MISSING_NIGHTS',
                                 'message': "Cannot determine number of nights. Defaulting to 1."})
            else:
                nights = int(nights_raw)

            ef_entry = GROUND_TRAVEL_FACTORS['hotel']
            ef = ef_entry['factor']
            ef_source = ef_entry['source']
            co2e_kg = nights * ef

            yield {
                'record': {
                    'scope': '3',
                    'category': 'Business Travel',
                    'subcategory': 'Hotel',
                    'fuel_type': 'hotel',
                    'raw_quantity': float(nights),
                    'raw_unit': 'room-nights',
                    'quantity_normalized': float(nights),
                    'normalized_unit': 'room-nights',
                    'quantity_co2e_kg': co2e_kg,
                    'emission_factor': ef,
                    'emission_factor_source': ef_source,
                    'period_start': period_start,
                    'period_end': period_end,
                    'source_system_id': trip_id,
                    'facility_code': employee_id,
                    'description': f"Hotel: {vendor or 'Unknown'} ({nights} nights)",
                    'flags': flags,
                    'raw_data': {**raw_data, '_nights': nights},
                },
                'warnings': warnings,
            }

        # ── Car rental segment ──────────────────────────────────────────
        elif segment_type in ('CAR', 'CAR RENTAL', 'CAR_RENTAL', 'RENTAL CAR', 'GROUND'):
            distance_km = _parse_float(get('distance_km', ''))
            if distance_km is None or distance_km <= 0:
                flags.append({'code': 'MISSING_DISTANCE',
                             'message': "Car rental distance not provided. CO2e cannot be calculated."})
                co2e_kg = None
                ef = None
                ef_source = ''
                norm_qty = 0
            else:
                ef_entry = GROUND_TRAVEL_FACTORS['car_average']
                ef = ef_entry['factor']
                ef_source = ef_entry['source']
                co2e_kg = distance_km * ef
                norm_qty = distance_km

            yield {
                'record': {
                    'scope': '3',
                    'category': 'Business Travel',
                    'subcategory': 'Car Rental',
                    'fuel_type': 'car',
                    'raw_quantity': distance_km or 0,
                    'raw_unit': 'km',
                    'quantity_normalized': norm_qty,
                    'normalized_unit': 'km',
                    'quantity_co2e_kg': co2e_kg,
                    'emission_factor': ef,
                    'emission_factor_source': ef_source,
                    'period_start': period_start,
                    'period_end': period_end,
                    'source_system_id': trip_id,
                    'facility_code': employee_id,
                    'description': f"Car rental: {vendor or 'Unknown'}",
                    'flags': flags,
                    'raw_data': raw_data,
                },
                'warnings': warnings,
            }

        # ── Rail segment ─────────────────────────────────────────────────
        elif segment_type in ('RAIL', 'TRAIN', 'RAILWAY'):
            distance_km = _parse_float(get('distance_km', ''))
            origin = get('origin', '')
            destination = get('destination', '')

            if distance_km is None or distance_km <= 0:
                # Try to infer distance from city codes if available
                dist, dist_src = get_flight_distance_km(origin, destination)
                if dist:
                    distance_km = dist
                    warnings.append({'code': 'DISTANCE_ESTIMATED',
                                    'message': f"Rail distance estimated from city codes: {dist:.0f} km"})
                else:
                    flags.append({'code': 'MISSING_DISTANCE',
                                 'message': "Rail distance not provided."})
                    co2e_kg = None
                    ef = None
                    ef_source = ''

            if distance_km and distance_km > 0:
                ef_entry = GROUND_TRAVEL_FACTORS['rail_national']
                ef = ef_entry['factor']
                ef_source = ef_entry['source']
                co2e_kg = distance_km * ef
            else:
                co2e_kg = None
                ef = None
                ef_source = ''

            yield {
                'record': {
                    'scope': '3',
                    'category': 'Business Travel',
                    'subcategory': 'Rail',
                    'fuel_type': 'rail',
                    'raw_quantity': distance_km or 0,
                    'raw_unit': 'km',
                    'quantity_normalized': distance_km or 0,
                    'normalized_unit': 'passenger-km',
                    'quantity_co2e_kg': co2e_kg,
                    'emission_factor': ef,
                    'emission_factor_source': ef_source,
                    'period_start': period_start,
                    'period_end': period_end,
                    'source_system_id': trip_id,
                    'facility_code': employee_id,
                    'description': f"Rail: {origin}→{destination} — {vendor}",
                    'flags': flags,
                    'raw_data': raw_data,
                },
                'warnings': warnings,
            }

        else:
            yield {
                'skipped': True,
                'row': row_num,
                'reason': f"Unknown segment type {segment_type!r}; skipped. "
                          f"Supported: Air, Hotel, Car, Rail.",
                'raw': raw_data,
            }
