"""Unit tests for spatial measurement calculations."""
import pytest
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, MultiLineString

from app.services.measurement import MeasurementService


def test_polygon_measurement_metric():
    # 100m x 100m square in a projected metric CRS
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    result = MeasurementService.calculate_measurement(poly, "EPSG:32618")

    assert result.supported is True
    assert result.geometry_type == "Polygon"
    assert result.area_sq_meters == pytest.approx(10000.0, rel=1e-3)
    assert result.area_hectares == pytest.approx(1.0, rel=1e-3)
    assert result.perimeter_meters == pytest.approx(400.0, rel=1e-3)


def test_linestring_measurement_metric():
    # 500m straight line
    line = LineString([(0, 0), (500, 0)])
    result = MeasurementService.calculate_measurement(line, "EPSG:32618")

    assert result.supported is True
    assert result.geometry_type == "LineString"
    assert result.length_meters == pytest.approx(500.0, rel=1e-3)
    assert result.length_kilometers == pytest.approx(0.5, rel=1e-3)


def test_point_measurement_unsupported_graceful():
    point = Point(10.0, 20.0)
    result = MeasurementService.calculate_measurement(point, "EPSG:4326")

    assert result.supported is False
    assert result.geometry_type == "Point"
    assert result.area_sq_meters is None
    assert result.length_meters is None
    assert "not applicable" in result.notes.lower()


def test_polygon_in_geographic_reprojected():
    # Small parcel in degrees (approx 100m x 100m near equator)
    # 0.0009 degrees is approx 100 meters
    poly = Polygon([(0, 0), (0.0009, 0), (0.0009, 0.0009), (0, 0.0009), (0, 0)])
    result = MeasurementService.calculate_measurement(poly, "EPSG:4326")

    assert result.supported is True
    assert result.projected_crs is not None
    assert "EPSG:326" in result.projected_crs
    # Area should be roughly ~10,000 m² (order of magnitude ~10^4), NOT degrees squared (~8e-7)
    assert 9000 < result.area_sq_meters < 11000


def test_empty_geometry_handled_gracefully():
    empty_poly = Polygon()
    result = MeasurementService.calculate_measurement(empty_poly, "EPSG:4326")
    assert result.supported is False
    assert "empty" in result.notes.lower()
