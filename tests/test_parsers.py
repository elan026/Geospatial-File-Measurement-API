"""Unit tests for Shapefile and KML parsers."""
import tempfile
import zipfile
from pathlib import Path
import pytest

from app.core.exceptions import InvalidFileFormatException
from app.services.parsers.kml import KMLParser
from app.services.parsers.shapefile import ShapefileParser


def test_kml_parser_polygons(sample_kml_polygons_path):
    parser = KMLParser()
    dataset = parser.parse(sample_kml_polygons_path, "polygons_sample.kml")

    assert dataset.crs == "EPSG:4326"
    assert len(dataset.features) == 2
    assert all(f.geometry.geom_type == "Polygon" for f in dataset.features)
    assert dataset.features[0].properties.get("name") == "Zone Alpha (Park Reserve)"
    assert dataset.features[0].properties.get("zone_type") == "Recreational"


def test_kml_parser_lines(sample_kml_lines_path):
    parser = KMLParser()
    dataset = parser.parse(sample_kml_lines_path, "linestrings_sample.kml")

    assert dataset.crs == "EPSG:4326"
    assert len(dataset.features) == 2
    assert all(f.geometry.geom_type == "LineString" for f in dataset.features)


def test_shapefile_parser_parcels(sample_shp_parcels_zip_path):
    parser = ShapefileParser()
    dataset = parser.parse(sample_shp_parcels_zip_path, "parcels.zip")

    assert len(dataset.features) == 2
    assert all(f.geometry.geom_type == "Polygon" for f in dataset.features)
    assert dataset.features[0].properties.get("name") == "Parcel A"


def test_shapefile_parser_missing_shp_raises():
    parser = ShapefileParser()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        with zipfile.ZipFile(f.name, "w") as zf:
            zf.writestr("test.txt", "not a shapefile")
        invalid_zip = Path(f.name)

    with pytest.raises(InvalidFileFormatException) as exc_info:
        parser.parse(invalid_zip, "invalid.zip")
    assert "does not contain any .shp file" in str(exc_info.value.message)


def test_shapefile_parser_bad_zip_raises():
    parser = ShapefileParser()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        f.write(b"not a valid zip file binary")
        bad_zip = Path(f.name)

    with pytest.raises(InvalidFileFormatException):
        parser.parse(bad_zip, "bad.zip")
