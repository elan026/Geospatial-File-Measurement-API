"""Unit tests for CRS detection and automatic projection selection."""
import pytest
from shapely.geometry import Polygon, LineString

from app.services.crs_service import CRSService


def test_utm_selection_northern_hemisphere():
    # New York City: ~ -74.0, 40.7 -> Zone 18 North -> EPSG:32618
    crs = CRSService.get_optimal_projected_crs_for_point(-73.98, 40.75)
    assert crs == "EPSG:32618"


def test_utm_selection_southern_hemisphere():
    # Sydney, Australia: ~ 151.2, -33.8 -> Zone 56 South -> EPSG:32756
    crs = CRSService.get_optimal_projected_crs_for_point(151.2, -33.86)
    assert crs == "EPSG:32756"


def test_polar_ups_selection():
    # Arctic (> 84N)
    assert CRSService.get_optimal_projected_crs_for_point(0.0, 85.0) == "EPSG:32661"
    # Antarctic (< -80S)
    assert CRSService.get_optimal_projected_crs_for_point(0.0, -85.0) == "EPSG:32761"


def test_is_geographic():
    assert CRSService.is_geographic("EPSG:4326") is True
    assert CRSService.is_geographic("EPSG:32618") is False
    assert CRSService.is_geographic("EPSG:3857") is False


def test_project_geometry_from_geographic_to_utm():
    # Create small polygon in San Francisco (Zone 10N: EPSG:32610)
    poly = Polygon([
        (-122.42, 37.77),
        (-122.41, 37.77),
        (-122.41, 37.78),
        (-122.42, 37.78),
        (-122.42, 37.77),
    ])
    proj_geom, proj_crs = CRSService.project_geometry(poly, "EPSG:4326")
    assert proj_crs == "EPSG:32610"
    # In projected metric UTM, area should be roughly ~800,000 to ~900,000 m² (not 0.0001 deg²)
    assert proj_geom.area > 500_000


def test_preserve_projected_crs():
    # Polygon already in UTM Zone 18N (EPSG:32618)
    poly = Polygon([(500000, 4500000), (500100, 4500000), (500100, 4500100), (500000, 4500000)])
    proj_geom, proj_crs = CRSService.project_geometry(poly, "EPSG:32618")
    assert proj_crs == "EPSG:32618"
    assert proj_geom.area == poly.area
