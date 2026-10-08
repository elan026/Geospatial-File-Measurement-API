"""Unit tests for spatial measurement calculations."""
import pytest
from shapely.geometry import Polygon, LineString, Point

from app.services.measurement import MeasurementService


def test_polygon_measurement_metric():
    poly = Polygon([(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)])
    result = MeasurementService.calculate_measurement(poly, "EPSG:32618")

    assert result is not None
    assert result.area == pytest.approx(10000.0, rel=1e-3)
    assert result.length is None


def test_linestring_measurement_metric():
    line = LineString([(0, 0), (500, 0)])
    result = MeasurementService.calculate_measurement(line, "EPSG:32618")

    assert result is not None
    assert result.length == pytest.approx(500.0, rel=1e-3)
    assert result.area is None


def test_point_measurement_none():
    point = Point(10.0, 20.0)
    result = MeasurementService.calculate_measurement(point, "EPSG:4326")
    assert result is None


def test_polygon_in_geographic_reprojected():
    # ~100m x 100m in degrees near equator
    poly = Polygon([(0, 0), (0.0009, 0), (0.0009, 0.0009), (0, 0.0009), (0, 0)])
    result = MeasurementService.calculate_measurement(poly, "EPSG:4326")

    assert result is not None
    assert 9000 < result.area < 11000


def test_empty_geometry_handled_gracefully():
    empty_poly = Polygon()
    result = MeasurementService.calculate_measurement(empty_poly, "EPSG:4326")
    assert result is None
