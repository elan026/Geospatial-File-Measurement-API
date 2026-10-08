"""Generate sample KML and zipped Shapefiles for testing and manual experimentation."""
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
import geopandas as gpd
from shapely.geometry import Polygon, LineString, Point


def generate_samples(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate Polygons KML (e.g. Central Park & Times Square vicinity, New York - EPSG:4326)
    kml_polygons = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>New York Survey Zones</name>
    <description>Sample polygons representing urban zones</description>
    <Placemark>
      <name>Zone Alpha (Park Reserve)</name>
      <description>Protected urban green space</description>
      <ExtendedData>
        <Data name="zone_type"><value>Recreational</value></Data>
        <Data name="surveyor"><value>Alice Green</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.9712,40.7831,0
              -73.9818,40.7681,0
              -73.9580,40.7648,0
              -73.9495,40.7798,0
              -73.9712,40.7831,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Zone Beta (Commercial Hub)</name>
      <description>High density commercial district</description>
      <ExtendedData>
        <Data name="zone_type"><value>Commercial</value></Data>
      </ExtendedData>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.9855,40.7580,0
              -73.9855,40.7520,0
              -73.9770,40.7520,0
              -73.9770,40.7580,0
              -73.9855,40.7580,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    (output_dir / "polygons_sample.kml").write_text(kml_polygons, encoding="utf-8")

    # 2. Generate LineStrings KML (e.g. Transit lines)
    kml_lines = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Transit Lines</name>
    <Placemark>
      <name>Broadway Corridor</name>
      <description>Main transit avenue</description>
      <LineString>
        <coordinates>
          -73.9851,40.7484,0
          -73.9868,40.7553,0
          -73.9830,40.7620,0
          -73.9760,40.7700,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Crosstown Boulevard</name>
      <LineString>
        <coordinates>
          -74.0000,40.7500,0
          -73.9700,40.7500,0
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
"""
    (output_dir / "linestrings_sample.kml").write_text(kml_lines, encoding="utf-8")

    # 3. Generate Mixed Geometries KML (Polygon, Line, Point)
    kml_mixed = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Mixed Geospatial Entities</name>
    <Placemark>
      <name>Survey Marker 101</name>
      <description>Geodetic benchmark station</description>
      <Point>
        <coordinates>-73.9800,40.7500,0</coordinates>
      </Point>
    </Placemark>
    <Placemark>
      <name>Pipeline Alpha</name>
      <LineString>
        <coordinates>
          -73.9800,40.7500,0
          -73.9700,40.7600,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Reservoir Boundary</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -73.9650,40.7850,0
              -73.9600,40.7800,0
              -73.9550,40.7850,0
              -73.9600,40.7900,0
              -73.9650,40.7850,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""
    (output_dir / "mixed_sample.kml").write_text(kml_mixed, encoding="utf-8")

    # 4. Generate ESRI Shapefile .zip (Polygon layer in WGS84)
    temp_shp_dir = Path(tempfile.mkdtemp(prefix="shp_gen_"))
    try:
        data = {
            "name": ["Parcel A", "Parcel B"],
            "owner": ["Acme Corp", "Beta LLC"],
            "zoning": ["Commercial", "Industrial"],
            "geometry": [
                Polygon([(-122.4194, 37.7749), (-122.4184, 37.7749), (-122.4184, 37.7739), (-122.4194, 37.7739)]),
                Polygon([(-122.4150, 37.7760), (-122.4130, 37.7760), (-122.4130, 37.7750), (-122.4150, 37.7750)]),
            ],
        }
        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326")
        shp_target = temp_shp_dir / "parcels.shp"
        gdf.to_file(shp_target, driver="ESRI Shapefile")

        # Zip it
        zip_path = output_dir / "sample_parcels_shapefile.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_shp_dir.glob("parcels.*"):
                zf.write(file_path, arcname=file_path.name)
    finally:
        shutil.rmtree(temp_shp_dir, ignore_errors=True)

    # 5. Generate ESRI Shapefile .zip with LineStrings
    temp_shp_lines = Path(tempfile.mkdtemp(prefix="shp_lines_"))
    try:
        line_data = {
            "road_name": ["Route 101", "Avenue 5"],
            "lanes": [4, 2],
            "geometry": [
                LineString([(-122.4200, 37.7700), (-122.4100, 37.7800), (-122.4000, 37.7900)]),
                LineString([(-122.4300, 37.7600), (-122.4250, 37.7650)]),
            ],
        }
        gdf_lines = gpd.GeoDataFrame(line_data, crs="EPSG:4326")
        gdf_lines.to_file(temp_shp_lines / "roads.shp", driver="ESRI Shapefile")

        zip_lines_path = output_dir / "sample_roads_shapefile.zip"
        with zipfile.ZipFile(zip_lines_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_shp_lines.glob("roads.*"):
                zf.write(file_path, arcname=file_path.name)
    finally:
        shutil.rmtree(temp_shp_lines, ignore_errors=True)

    print(f"Generated sample datasets in {output_dir}")


if __name__ == "__main__":
    generate_samples(Path("samples"))
