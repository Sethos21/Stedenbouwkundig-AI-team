"""Read-only native RD validation; no repair, transform, storage or promotion."""
from dataclasses import dataclass
from decimal import Decimal
from math import isfinite

import shapely
from shapely.geometry import shape
from shapely.errors import GEOSException

from bvc_ai.domain.sources import CRSMetadata, GeometryRecord
from bvc_ai.domain.source_hashing import (
    CANONICALIZATION_VERSION, geometry_structural_hash,
    normalize_crs_identifier, strict_json,
)

VALIDATOR_VERSION = "bvc-source-validation-v1"
CANONICAL_CRS = "EPSG:28992"
SUPPORTED_TYPES = frozenset({"Point", "LineString", "Polygon", "MultiPolygon"})


def validate_crs(metadata, *, source_crs=None):
    if not isinstance(metadata, CRSMetadata):
        raise ValueError("Explicit CRS metadata required")
    metadata.__post_init__()
    if normalize_crs_identifier(metadata.crs) != CANONICAL_CRS:
        raise ValueError("Only native EPSG:28992 is supported; transformation unavailable")
    if metadata.axis_order != ("easting", "northing"):
        raise ValueError("RD axis order must be easting, northing")
    if metadata.units != "metres":
        raise ValueError("RD units must be metres")
    if type(metadata.dimension) is not int or metadata.dimension != 2:
        raise ValueError("Only dimension 2 supported")
    if source_crs is not None and normalize_crs_identifier(source_crs) != CANONICAL_CRS:
        raise ValueError("Source response CRS contradicts geometry CRS")
    return CANONICAL_CRS


def _position(value):
    if type(value) is not list or len(value) != 2:
        raise ValueError("Exactly two coordinates per position required")
    for number in value:
        if type(number) not in (int, float, Decimal):
            raise ValueError("Numeric coordinates required; booleans are not numbers")
        try:
            converted = float(number)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Coordinate outside GEOS numeric range") from exc
        if not isfinite(converted) or (number != 0 and converted == 0):
            raise ValueError("Non-finite or underflowing coordinate")


def _positions(values, minimum):
    if type(values) is not list or len(values) < minimum:
        raise ValueError("Too few positions or wrong coordinate nesting")
    for value in values:
        _position(value)


def _polygon(rings):
    if type(rings) is not list or not rings:
        raise ValueError("Non-empty polygon rings required")
    for ring in rings:
        _positions(ring, 4)
        if ring[0] != ring[-1]:
            raise ValueError("Polygon rings must already be closed")
        if len({tuple(position) for position in ring[:-1]}) < 3:
            raise ValueError("Ring requires three distinct vertices")


def validate_geometry(geometry_json):
    """Validate structure before GEOS can implicitly close rings/drop dimensions."""
    geometry = strict_json(geometry_json)
    if type(geometry) is not dict or set(geometry) != {"type", "coordinates"}:
        raise ValueError("Non-null geometry object with type and coordinates required")
    kind = geometry["type"]
    if type(kind) is not str or kind not in SUPPORTED_TYPES:
        raise ValueError("Unsupported geometry type")
    coordinates = geometry["coordinates"]
    if kind == "Point":
        _position(coordinates)
    elif kind == "LineString":
        _positions(coordinates, 2)
    elif kind == "Polygon":
        _polygon(coordinates)
    else:
        if type(coordinates) is not list or not coordinates:
            raise ValueError("Non-empty MultiPolygon required")
        for polygon in coordinates:
            _polygon(polygon)
    try:
        engine_geometry = shape(geometry)
        if engine_geometry.is_empty or not shapely.is_valid(engine_geometry):
            raise ValueError("Invalid geometry: " + shapely.is_valid_reason(engine_geometry))
    except (GEOSException, TypeError, OverflowError) as exc:
        raise ValueError("Geometry rejected by GEOS") from exc
    return kind


@dataclass(frozen=True)
class GeometryValidation:
    geometry_type: str
    canonical_crs: str
    structural_hash: str
    validator_version: str = VALIDATOR_VERSION
    shapely_version: str = shapely.__version__
    geos_version: str = shapely.geos_version_string


def validate_geometry_record(record, *, source_crs=None):
    if not isinstance(record, GeometryRecord):
        raise ValueError("GeometryRecord required")
    record.__post_init__()
    crs = validate_crs(record.crs_metadata, source_crs=source_crs)
    kind = validate_geometry(record.geometry_json)
    if record.canonicalization_version != CANONICALIZATION_VERSION:
        raise ValueError("Unsupported geometry canonicalization version")
    computed = geometry_structural_hash(record.geometry_json, record.crs_metadata)
    if computed != record.geometry_structural_hash:
        raise ValueError("Geometry structural hash mismatch")
    return GeometryValidation(kind, crs, computed)
