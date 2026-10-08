"""Geometry measurement calculation engine."""
from shapely.geometry.base import BaseGeometry

from app.models.schemas import Measurement
from app.services.crs_service import CRSService
from app.core.logging import logger


class MeasurementService:
    """Calculates spatial measurements for supported geometries using metric projections."""

    POLYGON_TYPES = {"Polygon", "MultiPolygon"}
    LINE_TYPES = {"LineString", "MultiLineString", "LinearRing"}
    POINT_TYPES = {"Point", "MultiPoint"}

    @classmethod
    def calculate_measurement(
        cls, geometry: BaseGeometry, source_crs: str
    ) -> Measurement | None:
        """
        Calculate measurement for supported geometries.
        - Polygon / MultiPolygon -> Area
        - LineString / MultiLineString -> Length
        - Point / Unsupported -> None
        """
        geom_type = geometry.geom_type

        # Point geometries: no measurement required
        if geom_type in cls.POINT_TYPES or geometry.is_empty:
            return None

        # Polygon geometries: calculate Area
        if geom_type in cls.POLYGON_TYPES:
            try:
                projected_geom, _ = CRSService.project_geometry(geometry, source_crs)
                return Measurement(area=round(projected_geom.area, 2))
            except Exception as exc:
                logger.warning("Error calculating polygon area: %s", exc)
                return None

        # LineString geometries: calculate Length
        if geom_type in cls.LINE_TYPES:
            try:
                projected_geom, _ = CRSService.project_geometry(geometry, source_crs)
                return Measurement(length=round(projected_geom.length, 2))
            except Exception as exc:
                logger.warning("Error calculating line length: %s", exc)
                return None

        # Graceful handling for other/unsupported geometries
        return None
