"""Coordinate Reference System (CRS) detection, transformation, and projection service."""
import math
from functools import lru_cache
import pyproj
from shapely.geometry.base import BaseGeometry
import shapely.ops

from app.core.logging import logger
from app.core.exceptions import FileProcessingException


@lru_cache(maxsize=128)
def get_cached_transformer(source_crs_str: str, target_crs_str: str) -> pyproj.Transformer:
    """Cache pyproj Transformer instances to avoid repeated expensive initialization."""
    return pyproj.Transformer.from_crs(source_crs_str, target_crs_str, always_xy=True)


class CRSService:
    """Service to inspect, normalize, and reproject geospatial features to planar coordinate systems."""

    @staticmethod
    def normalize_crs_string(crs_input: any) -> str:
        """Parse arbitrary CRS representation (EPSG int, WKT, dict, pyproj CRS) into a standard string."""
        if not crs_input:
            return "EPSG:4326"

        try:
            crs_obj = pyproj.CRS.from_user_input(crs_input)
            auth = crs_obj.to_authority()
            if auth:
                return f"{auth[0]}:{auth[1]}"
            # If no authority code, use EPSG if possible or short representation
            epsg = crs_obj.to_epsg()
            if epsg:
                return f"EPSG:{epsg}"
            return crs_obj.to_string()
        except Exception as exc:
            logger.warning("Failed to parse CRS '%s', falling back to EPSG:4326: %s", crs_input, exc)
            return "EPSG:4326"

    @staticmethod
    def is_geographic(crs_str: str) -> bool:
        """Determine if a coordinate system is geographic (angular units such as degrees)."""
        try:
            crs_obj = pyproj.CRS.from_user_input(crs_str)
            return crs_obj.is_geographic
        except Exception:
            # Fallback assumption for EPSG:4326 / WGS84
            return "4326" in str(crs_str) or "WGS" in str(crs_str).upper()

    @staticmethod
    def get_optimal_projected_crs_for_point(lon: float, lat: float) -> str:
        """
        Determine the optimal metric projected CRS (UTM or UPS) for a given longitude and latitude.
        
        Strategy:
        - Polar North (> 84°N): Universal Polar Stereographic North (EPSG:32661)
        - Polar South (< -80°S): Universal Polar Stereographic South (EPSG:32761)
        - Standard Earth: Universal Transverse Mercator (UTM Zone 1 to 60)
          UTM Zone = floor((lon + 180) / 6) + 1
          Northern Hemisphere: EPSG 32600 + zone
          Southern Hemisphere: EPSG 32700 + zone
        """
        # Clamp coordinates to valid spherical boundaries
        lon = max(-180.0, min(180.0, lon))
        lat = max(-90.0, min(90.0, lat))

        if lat > 84.0:
            return "EPSG:32661"  # UPS North
        if lat < -80.0:
            return "EPSG:32761"  # UPS South

        zone = int(math.floor((lon + 180.0) / 6.0)) + 1
        zone = max(1, min(60, zone))

        if lat >= 0.0:
            epsg_code = 32600 + zone
        else:
            epsg_code = 32700 + zone

        return f"EPSG:{epsg_code}"

    @classmethod
    def project_geometry(
        cls, geometry: BaseGeometry, source_crs: str, target_crs: str | None = None
    ) -> tuple[BaseGeometry, str]:
        """
        Project a Shapely geometry from its source CRS to an appropriate metric projected CRS.
        
        If source CRS is geographic (degrees), it reprojects to the local UTM zone based on geometry centroid.
        If source CRS is Web Mercator (EPSG:3857), it reprojects to local UTM to eliminate high-latitude area distortion.
        If source CRS is already an accurate projected system, it returns the geometry as-is.
        
        Returns:
            (projected_geometry, projected_crs_string)
        """
        if geometry.is_empty:
            return geometry, source_crs

        norm_source_crs = cls.normalize_crs_string(source_crs)
        is_geo = cls.is_geographic(norm_source_crs)

        # Handle Web Mercator specifically due to massive metric distortion
        is_web_mercator = "3857" in norm_source_crs

        if not is_geo and not is_web_mercator and target_crs is None:
            # Already a valid projected CRS in planar metric/linear units
            return geometry, norm_source_crs

        # If target CRS wasn't provided, select optimal projected CRS
        if not target_crs:
            if is_geo:
                centroid = geometry.centroid
                target_crs = cls.get_optimal_projected_crs_for_point(centroid.x, centroid.y)
            elif is_web_mercator:
                # Convert centroid to WGS84 first to find appropriate UTM zone
                to_wgs84 = get_cached_transformer(norm_source_crs, "EPSG:4326")
                centroid = geometry.centroid
                geo_lon, geo_lat = to_wgs84.transform(centroid.x, centroid.y)
                target_crs = cls.get_optimal_projected_crs_for_point(geo_lon, geo_lat)
            else:
                target_crs = norm_source_crs

        if norm_source_crs == target_crs:
            return geometry, target_crs

        try:
            transformer = get_cached_transformer(norm_source_crs, target_crs)
            projected_geom = shapely.ops.transform(transformer.transform, geometry)
            return projected_geom, target_crs
        except Exception as exc:
            logger.error(
                "Error projecting geometry from %s to %s: %s",
                norm_source_crs,
                target_crs,
                exc,
            )
            raise FileProcessingException(
                f"Failed to project geometry from {norm_source_crs} to {target_crs}: {str(exc)}"
            )
