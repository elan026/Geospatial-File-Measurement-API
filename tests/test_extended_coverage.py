"""Additional tests for XML parsing fallback, GeometryCollections, and security."""
import tempfile
import zipfile
from pathlib import Path
import pytest
from shapely.geometry import MultiPolygon, Polygon, MultiLineString, LineString, GeometryCollection, Point

from app.core.exceptions import InvalidFileFormatException
from app.services.crs_service import CRSService
from app.services.measurement import MeasurementService
from app.services.parsers.kml import KMLParser
from app.services.parsers.shapefile import ShapefileParser


def test_kml_xml_parser_fallback_with_holes_and_multigeometry():
    kml_xml = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Donut Polygon</name>
      <ExtendedData>
        <Data name="donor"><value>Philanthropist</value></Data>
        <SimpleData name="category">Urban</SimpleData>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>0,0,0 10,0,0 10,10,0 0,10,0 0,0,0</coordinates>
          </LinearRing>
        </outerBoundaryIs>
        <innerBoundaryIs>
          <LinearRing>
            <coordinates>2,2,0 8,2,0 8,8,0 2,8,0 2,2,0</coordinates>
          </LinearRing>
        </innerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Compound MultiGeometry</name>
      <MultiGeometry>
        <Point><coordinates>1,1,0</coordinates></Point>
        <LineString><coordinates>0,0,0 2,2,0</coordinates></LineString>
        <Polygon>
          <outerBoundaryIs>
            <LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing>
          </outerBoundaryIs>
        </Polygon>
      </MultiGeometry>
    </Placemark>
  </Document>
</kml>
"""
    with tempfile.NamedTemporaryFile(suffix=".kml", delete=False, mode="w", encoding="utf-8") as f:
        f.write(kml_xml)
        tmp_kml = Path(f.name)

    parser = KMLParser()
    dataset = parser._parse_with_xml(tmp_kml, "donut.kml")

    assert len(dataset.features) == 2
    donut_feat = dataset.features[0]
    assert donut_feat.geometry.geom_type == "Polygon"
    assert len(donut_feat.geometry.interiors) == 1
    assert donut_feat.properties.get("donor") == "Philanthropist"
    assert donut_feat.properties.get("category") == "Urban"

    mg_feat = dataset.features[1]
    assert mg_feat.geometry.geom_type == "GeometryCollection"


def test_measurement_multipolygon_and_multilinestring():
    # MultiPolygon
    p1 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    p2 = Polygon([(20, 20), (30, 20), (30, 30), (20, 30), (20, 20)])
    mp = MultiPolygon([p1, p2])
    res_mp = MeasurementService.calculate_measurement(mp, "EPSG:32618")
    assert res_mp is not None
    assert res_mp.area == pytest.approx(200.0, rel=1e-3)

    # MultiLineString
    l1 = LineString([(0, 0), (10, 0)])
    l2 = LineString([(20, 0), (35, 0)])
    mls = MultiLineString([l1, l2])
    res_mls = MeasurementService.calculate_measurement(mls, "EPSG:32618")
    assert res_mls is not None
    assert res_mls.length == pytest.approx(25.0, rel=1e-3)


def test_web_mercator_reprojection_accuracy():
    # Polygon in Web Mercator EPSG:3857
    # Near London (lat ~ 51.5)
    poly = Polygon([(0, 6700000), (1000, 6700000), (1000, 6701000), (0, 6701000), (0, 6700000)])
    proj_geom, proj_crs = CRSService.project_geometry(poly, "EPSG:3857")
    assert "EPSG:326" in proj_crs


def test_zip_slip_security_prevention():
    parser = ShapefileParser()
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as f:
        with zipfile.ZipFile(f.name, "w") as zf:
            # Dangerous path traversal
            zf.writestr("../../etc/passwd.shp", "malicious payload")
        evil_zip = Path(f.name)

    with pytest.raises(InvalidFileFormatException) as exc:
        parser.parse(evil_zip, "evil.zip")
    assert "path traversal" in str(exc.value.message).lower()
