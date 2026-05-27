"""
SAP fuel & procurement parser.

Format chosen: SAP flat file export (semicolon-delimited, German column headers).
This is the format produced by SAP transaction MB51 (Material Document List)
and SE16/SE16N table exports from MSEG (material document segments).

Why this format over IDoc or OData?
- IDoc requires an active integration point; most sustainability leads pull
  MB51/SE16 exports manually on a monthly cadence.
- OData (SAP Gateway) requires IT involvement and a live connection; out of scope
  for a file-upload ingestion prototype.
- Flat file is the realistic worst-case that we must handle robustly.

Real-world quirks handled:
- German column headers (MANDT, BUKRS, WERKS, MATNR, MAKTX, BLDAT, MENGE, MEINS, BWART, KOSTL)
- Date formats: YYYYMMDD (standard), DD.MM.YYYY (regional SAP settings)
- Numbers: German decimal comma (1.234,56) and US decimal point (1234.56)
- Trailing semicolons on some exports (extra empty column)
- Movement type filtering: we only want consumption records (261 = GI for order,
  201 = GI for cost center, 551 = GI for scrapping, 281 = GI for project).
  Goods receipts (101) are excluded — they represent procurement, not consumption.
- Unknown material numbers get flagged, not dropped.
"""

import io
import csv
import hashlib
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterator

from ingestion.emission_factors import (
    FUEL_FACTORS, SAP_UNIT_CANONICAL, map_sap_material_to_fuel, normalize_quantity
)

# Column header aliases — SAP can export with or without the MANDT prefix,
# and regional configurations sometimes use translated headers.
COLUMN_MAP = {
    # Standard German technical names
    'MANDT': 'client',
    'BUKRS': 'company_code',
    'WERKS': 'plant_code',
    'MATNR': 'material_number',
    'MAKTX': 'material_description',
    'BLDAT': 'document_date',
    'BUDAT': 'posting_date',
    'MENGE': 'quantity',
    'MEINS': 'unit_of_measure',
    'BWART': 'movement_type',
    'KOSTL': 'cost_center',
    'BKTXT': 'text',
    'WERKS_NAME': 'plant_name',
    # English equivalents (some SAP configs export English)
    'COMPANY CODE': 'company_code',
    'PLANT': 'plant_code',
    'MATERIAL': 'material_number',
    'MATERIAL DESCRIPTION': 'material_description',
    'DOCUMENT DATE': 'document_date',
    'POSTING DATE': 'posting_date',
    'QUANTITY': 'quantity',
    'UNIT': 'unit_of_measure',
    'MOVEMENT TYPE': 'movement_type',
    'COST CENTER': 'cost_center',
    'TEXT': 'text',
    'PLANT NAME': 'plant_name',
}

# Movement types that represent actual fuel consumption
CONSUMPTION_MOVEMENT_TYPES = {
    '201', '261', '281', '551', '601',
    '201',  # GI for cost center
    '261',  # GI for order (most common for plant fuel use)
    '281',  # GI for project
    '551',  # GI scrapping
}


def _normalize_number(raw: str) -> Decimal:
    """
    Handle both German (1.234,56) and US (1234.56) decimal formats.
    SAP frequently uses the German format for quantity fields.
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty quantity")
    # German format: dots as thousands separator, comma as decimal
    if ',' in raw and '.' in raw:
        if raw.rindex(',') > raw.rindex('.'):
            raw = raw.replace('.', '').replace(',', '.')
        else:
            raw = raw.replace(',', '')
    elif ',' in raw:
        raw = raw.replace(',', '.')
    return Decimal(raw)


def _parse_sap_date(raw: str) -> date:
    """Parse YYYYMMDD or DD.MM.YYYY or YYYY-MM-DD."""
    raw = raw.strip()
    if not raw:
        raise ValueError("Empty date")
    for fmt in ('%Y%m%d', '%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse SAP date: {raw!r}")


def _strip_leading_zeros(material_number: str) -> str:
    """SAP pads MATNR to 18 chars with leading zeros."""
    return material_number.lstrip('0') or '0'


def _map_headers(raw_headers: list[str]) -> dict[str, int]:
    """Return {canonical_name: column_index} for known headers."""
    result = {}
    for i, h in enumerate(raw_headers):
        canonical = COLUMN_MAP.get(h.strip().upper())
        if canonical:
            result[canonical] = i
    return result


def parse_sap_csv(file_content: bytes) -> Iterator[dict]:
    """
    Yields parsed row dicts or error dicts.
    Each dict has either 'record' (success) or 'error' keys.
    """
    text = file_content.decode('utf-8', errors='replace')
    # SAP exports sometimes use semicolons, sometimes tabs
    delimiter = ';' if text.count(';') > text.count('\t') else '\t'
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)

    headers = None
    col_map = {}

    for row_num, row in enumerate(reader, start=1):
        # Strip trailing empty fields from trailing delimiters
        while row and row[-1] == '':
            row.pop()

        if not row:
            continue

        if headers is None:
            headers = row
            col_map = _map_headers(headers)
            if 'quantity' not in col_map or 'material_description' not in col_map:
                yield {'error': f"Row {row_num}: Cannot identify required columns. "
                               f"Found: {headers}. Expected MENGE/QUANTITY and MAKTX."}
                return
            continue

        def get(field: str, default='') -> str:
            idx = col_map.get(field)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        # Movement type filter
        mvt = get('movement_type', '261')
        # If movement_type column is present but value not in consumption types, skip
        if 'movement_type' in col_map and mvt and mvt not in CONSUMPTION_MOVEMENT_TYPES:
            yield {
                'skipped': True,
                'row': row_num,
                'reason': f"Movement type {mvt!r} is not a consumption record; skipped.",
                'raw': dict(zip(headers, row)),
            }
            continue

        # Parse quantity
        try:
            raw_qty = _normalize_number(get('quantity', '0'))
        except (ValueError, InvalidOperation) as e:
            yield {'error': f"Row {row_num}: Cannot parse quantity {get('quantity')!r}: {e}",
                   'row': row_num, 'raw': dict(zip(headers, row))}
            continue

        if raw_qty <= 0:
            yield {'error': f"Row {row_num}: Non-positive quantity {raw_qty}; skipped.",
                   'row': row_num, 'raw': dict(zip(headers, row))}
            continue

        # Parse date
        date_raw = get('document_date') or get('posting_date')
        try:
            doc_date = _parse_sap_date(date_raw)
        except ValueError as e:
            yield {'error': f"Row {row_num}: Date parse error: {e}", 'row': row_num}
            continue

        raw_unit = SAP_UNIT_CANONICAL.get(get('unit_of_measure', 'L').upper(), get('unit_of_measure', 'L'))
        mat_desc = get('material_description')
        mat_num = _strip_leading_zeros(get('material_number', ''))
        plant = get('plant_code', '')
        plant_name = get('plant_name', plant)
        cost_center = get('cost_center', '')
        text = get('text', '')

        fuel_type = map_sap_material_to_fuel(mat_desc)
        warnings = []

        if fuel_type is None:
            warnings.append({
                'code': 'UNKNOWN_MATERIAL',
                'message': f"Material {mat_num!r} ({mat_desc!r}) not in fuel lookup table. "
                           f"Record retained but CO2e will be null. "
                           f"Add a fuel mapping or reject this row.",
            })

        # Normalize unit
        norm_qty, norm_unit = normalize_quantity(float(raw_qty), raw_unit, fuel_type or 'diesel')

        # Calculate CO2e if fuel type is known
        co2e_kg = None
        ef = None
        ef_source = ''
        if fuel_type and fuel_type in FUEL_FACTORS:
            entry = FUEL_FACTORS[fuel_type]
            ef = entry['factor']
            ef_source = entry['source']
            co2e_kg = float(norm_qty) * ef

        # Auto-flag rules
        flags = []
        if fuel_type is None:
            flags.append({'code': 'UNKNOWN_MATERIAL', 'message': f"Unknown material: {mat_desc!r}"})
        if co2e_kg and co2e_kg > 500_000:
            flags.append({'code': 'LARGE_QUANTITY',
                          'message': f"CO2e {co2e_kg:.0f} kg is unusually large — verify quantity."})
        if not plant:
            flags.append({'code': 'MISSING_PLANT', 'message': "No plant code; cannot determine facility."})

        yield {
            'record': {
                'scope': FUEL_FACTORS.get(fuel_type, {}).get('scope', '1') if fuel_type else '1',
                'category': FUEL_FACTORS.get(fuel_type, {}).get('category', 'Stationary Combustion') if fuel_type else 'Stationary Combustion',
                'fuel_type': fuel_type or '',
                'raw_quantity': float(raw_qty),
                'raw_unit': raw_unit,
                'quantity_normalized': norm_qty,
                'normalized_unit': norm_unit,
                'quantity_co2e_kg': co2e_kg,
                'emission_factor': ef,
                'emission_factor_source': ef_source,
                'period_start': doc_date,
                'period_end': doc_date,
                'source_system_id': mat_num,
                'facility_code': plant,
                'description': f"{mat_desc} — {plant_name} — {text}".strip(' —'),
                'flags': flags,
                'raw_data': dict(zip(headers, row)),
            },
            'warnings': warnings,
        }
