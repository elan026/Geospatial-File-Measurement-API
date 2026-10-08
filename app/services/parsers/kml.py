"""KML file parser supporting pyogrio and safe XML element fallback parsing."""
import re
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element
import defusedxml.ElementTree as ET
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, MultiLineString, GeometryCollection
from shapely.geometry.base import BaseGeometry
import pyogrio

from app.core.exceptions import InvalidFileFormatException, FileProcessingException
from app.core.logging import logger
from app.services.parsers.base import BaseGeoParser, ParsedGeoDataset, RawFeature
from app.services.parsers.shapefile import sanitize_attributes


class KMLParser(BaseGeoParser):
    """Parses Keyhole Markup Language (.kml) files into geospatial datasets."""

    def parse(self, file_path: Path, original_filename: str) -> ParsedGeoDataset:
        # First attempt: pyogrio native KML driver
        try:
            return self._parse_with_pyogrio(file_path, original_filename)
        except Exception as pyogrio_exc:
            logger.info("pyogrio KML read failed or skipped (%s). Falling back to XML parser.", pyogrio_exc)

        # Fallback: robust XML parser using defusedxml
        try:
            return self._parse_with_xml(file_path, original_filename)
        except Exception as xml_exc:
            logger.error("Failed to parse KML file with XML fallback: %s", xml_exc)
            raise FileProcessingException(f"Failed to parse KML file: {str(xml_exc)}")

    def _parse_with_pyogrio(self, file_path: Path, original_filename: str) -> ParsedGeoDataset:
        gdf = pyogrio.read_dataframe(str(file_path))
        features: list[RawFeature] = []

        for idx, row in gdf.iterrows():
            geom = row.get("geometry")
            if geom is None:
                continue

            props = row.drop(labels=["geometry"], errors="ignore").to_dict()
            cleaned_props = sanitize_attributes(props)
            if "Name" in cleaned_props and "name" not in cleaned_props:
                cleaned_props["name"] = cleaned_props["Name"]

            feature_id = row.get("Name") or row.get("name") or row.get("id") or str(idx)
            features.append(
                RawFeature(
                    feature_id=str(feature_id),
                    geometry=geom,
                    properties=cleaned_props,
                )
            )

        return ParsedGeoDataset(
            features=features,
            crs="EPSG:4326",  # Standard KML is always WGS84
            file_type="KML (.kml)",
            filename=original_filename,
        )

    def _parse_with_xml(self, file_path: Path, original_filename: str) -> ParsedGeoDataset:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError as err:
            raise InvalidFileFormatException(f"Invalid XML syntax in KML file: {err}")

        # Strip XML namespaces for uniform querying
        self._strip_namespaces(root)

        features: list[RawFeature] = []
        placemarks = root.findall(".//Placemark")

        for idx, pm in enumerate(placemarks):
            # Extract basic Placemark attributes
            name_el = pm.find("name")
            desc_el = pm.find("description")
            feature_name = name_el.text.strip() if name_el is not None and name_el.text else f"feature_{idx}"
            
            properties: dict[str, Any] = {}
            if name_el is not None and name_el.text:
                properties["name"] = name_el.text.strip()
            if desc_el is not None and desc_el.text:
                properties["description"] = desc_el.text.strip()

            # Extract ExtendedData
            ext_data = pm.find("ExtendedData")
            if ext_data is not None:
                for data_el in ext_data.findall(".//Data"):
                    d_name = data_el.attrib.get("name")
                    val_el = data_el.find("value")
                    if d_name and val_el is not None and val_el.text:
                        properties[d_name] = val_el.text.strip()
                for sdata_el in ext_data.findall(".//SimpleData"):
                    s_name = sdata_el.attrib.get("name")
                    if s_name and sdata_el.text:
                        properties[s_name] = sdata_el.text.strip()

            # Parse Geometry
            geom = self._extract_geometry_from_placemark(pm)
            if geom is not None and not geom.is_empty:
                features.append(
                    RawFeature(
                        feature_id=feature_name or str(idx),
                        geometry=geom,
                        properties=properties,
                    )
                )

        return ParsedGeoDataset(
            features=features,
            crs="EPSG:4326",
            file_type="KML (.kml)",
            filename=original_filename,
        )

    def _extract_geometry_from_placemark(self, placemark: Element) -> BaseGeometry | None:
        # Check MultiGeometry first to prevent matching nested child geometries prematurely
        mg_el = placemark.find(".//MultiGeometry")
        if mg_el is not None:
            geoms = []
            for child in mg_el:
                tag = child.tag
                if tag == "Polygon":
                    p = self._parse_polygon(child)
                    if p:
                        geoms.append(p)
                elif tag == "LineString":
                    coords = self._parse_coordinates(child.findtext("coordinates", ""))
                    if len(coords) >= 2:
                        geoms.append(LineString(coords))
                elif tag == "Point":
                    coords = self._parse_coordinates(child.findtext("coordinates", ""))
                    if coords:
                        geoms.append(Point(coords[0]))
            if geoms:
                return GeometryCollection(geoms)

        # Check standalone Polygon
        poly_el = placemark.find(".//Polygon")
        if poly_el is not None:
            return self._parse_polygon(poly_el)

        # Check standalone LineString
        line_el = placemark.find(".//LineString")
        if line_el is not None:
            coords = self._parse_coordinates(line_el.findtext("coordinates", ""))
            if len(coords) >= 2:
                return LineString(coords)

        # Check standalone Point
        point_el = placemark.find(".//Point")
        if point_el is not None:
            coords = self._parse_coordinates(point_el.findtext("coordinates", ""))
            if coords:
                return Point(coords[0])

        return None

    def _parse_polygon(self, poly_el: Element) -> Polygon | None:
        outer_coords = self._parse_coordinates(
            poly_el.findtext(".//outerBoundaryIs/LinearRing/coordinates", "")
        )
        if len(outer_coords) < 3:
            return None

        # Holes / inner rings
        holes = []
        for inner in poly_el.findall(".//innerBoundaryIs/LinearRing/coordinates"):
            inner_coords = self._parse_coordinates(inner.text or "")
            if len(inner_coords) >= 3:
                holes.append(inner_coords)

        return Polygon(shell=outer_coords, holes=holes)

    def _parse_coordinates(self, coords_text: str) -> list[tuple[float, float]]:
        """Parse KML coordinate tuples: 'lon,lat[,alt] lon,lat...'"""
        tuples = []
        for token in coords_text.strip().split():
            parts = token.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    tuples.append((lon, lat))
                except ValueError:
                    continue
        return tuples

    def _strip_namespaces(self, element: Element) -> None:
        """Recursively strip XML namespaces for clean tag matching."""
        if "}" in element.tag:
            element.tag = element.tag.split("}", 1)[1]
        for child in element:
            self._strip_namespaces(child)
