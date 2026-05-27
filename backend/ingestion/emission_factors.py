"""
Emission factors used for CO2e calculation.

Sources:
- DEFRA 2023 Conversion Factors (UK Government)
- EPA 2023 Emission Factors for GHG Inventories
- IEA CO2 Emissions from Fuel Combustion
- IPCC AR6 GWP values (100-year)

All factors are in kg CO2e per unit stated.
These are point-in-time factors. In production, factors would be stored in
the database so they can be versioned and updated without code changes.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Scope 1: Direct combustion (stationary + mobile)
# ─────────────────────────────────────────────────────────────────────────────

FUEL_FACTORS = {
    'diesel': {
        'factor': 2.68,        # kg CO2e / litre
        'canonical_unit': 'L',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'natural_gas': {
        'factor': 2.02,        # kg CO2e / m³ (at 10.55 kWh/m³, 0.18315 kg/kWh)
        'canonical_unit': 'M3',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'petrol': {
        'factor': 2.31,        # kg CO2e / litre
        'canonical_unit': 'L',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Mobile Combustion',
    },
    'lpg': {
        'factor': 1.51,        # kg CO2e / litre
        'canonical_unit': 'L',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'hfo': {
        'factor': 3.35,        # kg CO2e / kg (heavy fuel oil)
        'canonical_unit': 'KG',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'heating_oil': {
        'factor': 2.54,        # kg CO2e / litre
        'canonical_unit': 'L',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'kerosene': {
        'factor': 2.55,        # kg CO2e / litre
        'canonical_unit': 'L',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Mobile Combustion',
    },
    'coal': {
        'factor': 2.42,        # kg CO2e / kg (thermal coal)
        'canonical_unit': 'KG',
        'source': 'DEFRA 2023',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
    'biomass': {
        'factor': 0.0,         # CO2-neutral under GHG Protocol; biogenic CO2 reported separately
        'canonical_unit': 'KG',
        'source': 'GHG Protocol',
        'scope': '1',
        'category': 'Stationary Combustion',
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Scope 2: Purchased electricity — location-based grid factors (kg CO2e / kWh)
# ─────────────────────────────────────────────────────────────────────────────

GRID_FACTORS = {
    'DE': {'factor': 0.434, 'source': 'IEA 2023 / UBA 2023'},
    'GB': {'factor': 0.233, 'source': 'DEFRA 2023'},
    'US': {'factor': 0.386, 'source': 'EPA eGRID 2022 national avg'},
    'IN': {'factor': 0.820, 'source': 'CEA India 2021-22'},
    'FR': {'factor': 0.052, 'source': 'IEA 2023 (nuclear-heavy)'},
    'CN': {'factor': 0.581, 'source': 'IEA 2022'},
    'AU': {'factor': 0.790, 'source': 'DCCEEW 2022'},
    'NL': {'factor': 0.408, 'source': 'IEA 2023'},
    'SE': {'factor': 0.013, 'source': 'IEA 2023 (hydro/nuclear)'},
    'NO': {'factor': 0.026, 'source': 'IEA 2023 (hydro)'},
    'DEFAULT': {'factor': 0.500, 'source': 'IEA global average (approximate)'},
}


def get_grid_factor(country_code: str, custom: float = None):
    """Returns (factor_kg_per_kwh, source_string)."""
    if custom is not None:
        return float(custom), 'Custom market-based factor'
    entry = GRID_FACTORS.get(country_code.upper(), GRID_FACTORS['DEFAULT'])
    return entry['factor'], entry['source']


# ─────────────────────────────────────────────────────────────────────────────
# Scope 3: Business travel (kg CO2e / passenger-km, including RFI)
# Radiative Forcing Index of 1.9 is applied for air travel per DEFRA 2023.
# ─────────────────────────────────────────────────────────────────────────────

AIR_FACTORS = {
    # (haul_type, cabin_class) → kg CO2e / passenger-km
    ('short', 'economy'):   {'factor': 0.255, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('short', 'business'):  {'factor': 0.369, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('short', 'first'):     {'factor': 0.369, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('long', 'economy'):    {'factor': 0.195, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('long', 'business'):   {'factor': 0.429, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('long', 'first'):      {'factor': 0.583, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
    ('long', 'premium'):    {'factor': 0.295, 'source': 'DEFRA 2023 (incl. RFI 1.9)'},
}

# Short-haul threshold: DEFRA defines short-haul as < 3,700 km
AIR_SHORTHAUL_KM = 3700

GROUND_TRAVEL_FACTORS = {
    'hotel': {
        'factor': 31.7,        # kg CO2e / room-night (global average)
        'unit': 'room-night',
        'source': 'DEFRA 2023',
    },
    'car_petrol_medium': {
        'factor': 0.168,       # kg CO2e / km
        'unit': 'km',
        'source': 'DEFRA 2023',
    },
    'car_diesel_medium': {
        'factor': 0.163,
        'unit': 'km',
        'source': 'DEFRA 2023',
    },
    'car_average': {
        'factor': 0.168,
        'unit': 'km',
        'source': 'DEFRA 2023 (medium petrol, used when type unknown)',
    },
    'rail_national': {
        'factor': 0.041,       # kg CO2e / passenger-km (national average)
        'unit': 'km',
        'source': 'DEFRA 2023',
    },
    'rail_international': {
        'factor': 0.006,       # High-speed international rail
        'unit': 'km',
        'source': 'DEFRA 2023',
    },
    'taxi': {
        'factor': 0.211,
        'unit': 'km',
        'source': 'DEFRA 2023',
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Airport coordinates (lat, lon) for great-circle distance calculation
# ─────────────────────────────────────────────────────────────────────────────

AIRPORT_COORDS = {
    'JFK': (40.6413, -73.7781), 'LAX': (33.9425, -118.4081),
    'LHR': (51.4775, -0.4614),  'CDG': (49.0097, 2.5479),
    'DXB': (25.2532, 55.3657),  'SIN': (1.3644, 103.9915),
    'HKG': (22.3080, 113.9185), 'BOM': (19.0896, 72.8656),
    'DEL': (28.5665, 77.1031),  'SYD': (-33.9399, 151.1753),
    'NRT': (35.7720, 140.3929), 'FRA': (50.0379, 8.5622),
    'AMS': (52.3105, 4.7683),   'ORD': (41.9742, -87.9073),
    'ATL': (33.6407, -84.4277), 'DFW': (32.8998, -97.0403),
    'MIA': (25.7959, -80.2870), 'SFO': (37.6213, -122.3790),
    'BOS': (42.3656, -71.0096), 'SEA': (47.4502, -122.3088),
    'YYZ': (43.6777, -79.6248), 'MEX': (19.4363, -99.0721),
    'GRU': (-23.4356, -46.4731),'EZE': (-34.8222, -58.5358),
    'JNB': (-26.1367, 28.2411), 'NBO': (-1.3192, 36.9275),
    'CAI': (30.1219, 31.4056),  'SVO': (55.9726, 37.4146),
    'PEK': (40.0799, 116.6031), 'PVG': (31.1434, 121.8052),
    'ICN': (37.4602, 126.4407), 'BKK': (13.6900, 100.7501),
    'KUL': (2.7456, 101.7096),  'MNL': (14.5086, 121.0194),
    'MEL': (-37.6690, 144.8410),'AKL': (-37.0082, 174.7921),
    'MAD': (40.4936, -3.5668),  'BCN': (41.2974, 2.0833),
    'FCO': (41.8003, 12.2389),  'MXP': (45.6306, 8.7281),
    'ZRH': (47.4647, 8.5492),   'VIE': (48.1103, 16.5697),
    'CPH': (55.6180, 12.6508),  'ARN': (59.6519, 17.9186),
    'OSL': (60.1939, 11.1004),  'HEL': (60.3172, 24.9633),
    'DUB': (53.4213, -6.2701),  'MAN': (53.3537, -2.2750),
    'BHX': (52.4539, -1.7480),  'EDI': (55.9500, -3.3725),
    'BRU': (50.9010, 4.4844),   'LIS': (38.7742, -9.1342),
    'ATH': (37.9364, 23.9445),  'IST': (41.2608, 28.7418),
    'TLV': (32.0114, 34.8867),  'DOH': (25.2731, 51.6082),
    'AUH': (24.4330, 54.6511),  'RUH': (24.9576, 46.6988),
    'BLR': (13.1979, 77.7063),  'MAA': (12.9941, 80.1709),
    'HYD': (17.2403, 78.4294),  'CCU': (22.6520, 88.4463),
    'BBI': (20.2444, 85.8178),  'GOI': (15.3808, 73.8314),
    'AMD': (23.0772, 72.6347),  'LKO': (26.7606, 80.8893),
    'PAR': (48.8566, 2.3522),   # Paris city (for rail)
    'BER': (52.5200, 13.4050),  # Berlin city (for rail)
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in km."""
    import math
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def get_flight_distance_km(origin: str, destination: str) -> tuple:
    """
    Returns (distance_km, source) for a flight pair.
    source is 'calculated' if we computed it, 'unknown' if airports not found.
    Applies a 1.08 detour factor (DEFRA/ICAO recommendation) to account for
    actual routing vs great-circle.
    """
    o = AIRPORT_COORDS.get(origin.upper())
    d = AIRPORT_COORDS.get(destination.upper())
    if o and d:
        gc = haversine_km(o[0], o[1], d[0], d[1])
        return round(gc * 1.08, 1), 'calculated (haversine × 1.08 detour factor)'
    return None, 'unknown airport code'


def get_air_emission_factor(distance_km: float, cabin_class: str) -> tuple:
    """Returns (factor_kg_per_pkm, source)."""
    haul = 'short' if distance_km < AIR_SHORTHAUL_KM else 'long'
    cabin = cabin_class.lower().strip() if cabin_class else 'economy'
    cabin = 'economy' if cabin not in ('economy', 'business', 'first', 'premium') else cabin
    key = (haul, cabin)
    entry = AIR_FACTORS.get(key, AIR_FACTORS[('long', 'economy')])
    return entry['factor'], entry['source']


# ─────────────────────────────────────────────────────────────────────────────
# SAP material → fuel type mapping
# Match on lowercased material description (MAKTX) or material number prefix
# ─────────────────────────────────────────────────────────────────────────────

MATERIAL_FUEL_MAP = [
    # (substring to match in description.lower(), fuel_type)
    ('dieselkraftstoff', 'diesel'),
    ('diesel kraftstoff', 'diesel'),
    ('diesel', 'diesel'),
    ('erdgas', 'natural_gas'),
    ('natural gas', 'natural_gas'),
    ('benzin', 'petrol'),
    ('petrol', 'petrol'),
    ('gasoline', 'petrol'),
    ('fluessiggas', 'lpg'),
    ('flüssiggas', 'lpg'),
    ('lpg', 'lpg'),
    ('schweröl', 'hfo'),
    ('schwerol', 'hfo'),
    ('hfo', 'hfo'),
    ('heizöl', 'heating_oil'),
    ('heizol', 'heating_oil'),
    ('heating oil', 'heating_oil'),
    ('kerosin', 'kerosene'),
    ('kerosene', 'kerosene'),
    ('jet fuel', 'kerosene'),
    ('kohle', 'coal'),
    ('coal', 'coal'),
    ('biomasse', 'biomass'),
    ('biomass', 'biomass'),
    ('holzpellets', 'biomass'),
]

# SAP unit of measure → canonical unit
SAP_UNIT_CANONICAL = {
    'L': 'L', 'LTR': 'L', 'LITER': 'L', 'LT': 'L',
    'M3': 'M3', 'CBM': 'M3', 'KM3': 'M3',
    'KG': 'KG', 'KGM': 'KG',
    'T': 'T', 'TO': 'T', 'TNE': 'T',
    'KWH': 'KWH', 'KW': 'KWH',
    'MWH': 'MWH', 'GJ': 'GJ',
    'ST': 'EACH',  # pieces — shouldn't appear in fuel but may in error
}

# Conversions to canonical unit for emission factor matching
UNIT_TO_CANONICAL = {
    ('T', 'KG'): 1000.0,
    ('MWH', 'KWH'): 1000.0,
    ('GJ', 'KWH'): 277.778,
    ('GJ', 'M3'): 26.853,  # natural gas: 1 GJ ≈ 26.9 m³ (depends on calorific value)
}


def map_sap_material_to_fuel(description: str) -> str | None:
    d = (description or '').lower()
    for substring, fuel_type in MATERIAL_FUEL_MAP:
        if substring in d:
            return fuel_type
    return None


def normalize_quantity(quantity: float, from_unit: str, fuel_type: str) -> tuple:
    """
    Convert raw quantity + unit to the canonical unit for the given fuel type.
    Returns (normalized_quantity, canonical_unit).
    """
    canonical_for_fuel = FUEL_FACTORS.get(fuel_type, {}).get('canonical_unit', from_unit)
    key = (from_unit.upper(), canonical_for_fuel.upper())

    if from_unit.upper() == canonical_for_fuel.upper():
        return quantity, canonical_for_fuel

    factor = UNIT_TO_CANONICAL.get(key)
    if factor:
        return quantity * factor, canonical_for_fuel

    # No known conversion — return as-is and flag
    return quantity, from_unit
