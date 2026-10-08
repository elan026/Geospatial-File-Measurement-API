"""Geometry measurement calculation engine."""
from shapely.geometry.base import BaseGeometry
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, Point, MultiPoint

from app.models.schemas import MeasurementDetail
from app.services.crs_service import CRSService
from app.core.logging import logger


class MeasurementService:
    """Calculates spatial measurements (Area, Length) for geometries using metric projections."""

    POLYGON_TYPES = {"Polygon", "MultiPolygon"}
    LINE_TYPES = {"LineString", "MultiLineString", "LinearRing"}
    POINT_TYPES = {"Point", "MultiPoint"}

    @classmethod
    def calculate_measurement(
        cls, geometry: BaseGeometry, source_crs: str
    ) -> MeasurementDetail:
        """
        Calculates measurement for a geometry.
        
        Transforms geographic geometries to appropriate projected metric CRS before calculation.
        Gracefully handles unsupported geometries (Points, Collections, empty geometries).
        """
        geom_type = geometry.geom_type

        # Handle empty geometry
        if geometry.is_empty:
            return MeasurementDetail(
                geometry_type=geom_type,
                supported=False,
                notes="Geometry is empty.",
            )

        # Handle Point geometries
        if geom_type in cls.POINT_TYPES:
            return MeasurementDetail(
                geometry_type=geom_type,
                supported=False,
                notes="Point geometries have 0 dimensions; area and length measurements are not applicable.",
            )

        # Handle Polygon geometries
        if geom_type in cls.POLYGON_TYPES:
            try:
                projected_geom, proj_crs = CRSService.project_geometry(geometry, source_crs)
                area_m2 = projected_geom.area
                perimeter_m = projected_geom.length

                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=True,
                    projected_crs=proj_crs,
                    area_sq_meters=round(area_m2, 4),
                    area_hectares=round(area_m2 / 10_000.0, 6),
                    area_acres=round(area_m2 / 4_046.8564224, 6),
                    perimeter_meters=round(perimeter_m, 4),
                )
            except Exception as exc:
                logger.warning("Error calculating polygon area: %s", exc)
                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=False,
                    notes=f"Error projecting polygon for measurement: {str(exc)}",
                )

        # Handle LineString geometries
        if geom_type in cls.LINE_TYPES:
            try:
                projected_geom, proj_crs = CRSService.project_geometry(geometry, source_crs)
                length_m = projected_geom.length

                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=True,
                    projected_crs=proj_crs,
                    length_meters=round(length_m, 4),
                    length_kilometers=round(length_m / 1000.0, 6),
                )
            except Exception as exc:
                logger.warning("Error calculating line length: %s", exc)
                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=False,
                    notes=f"Error projecting line for measurement: {str(exc)}",
                )

        # Handle GeometryCollection or other unhandled types gracefully
        if geom_type == "GeometryCollection":
            # Attempt to sum sub-geometries
            total_area = 0.0
            total_len = 0.0
            has_area = False
            has_len = False
            last_proj_crs = None

            try:
                for sub_geom in geometry.geoms:
                    if sub_geom.geom_type in cls.POLYGON_TYPES:
                        proj_sub, p_crs = CRSService.project_geometry(sub_geom, source_crs)
                        total_area += proj_sub.area
                        has_area = True
                        last_proj_crs = p_crs
                    elif sub_geom.geom_type in cls.LINE_TYPES:
                        proj_sub, p_crs = CRSService.project_geometry(sub_geom, source_crs)
                        total_len += proj_sub.length
                        has_len = True
                        last_proj_crs = p_crs

                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=has_area or has_len,
                    projected_crs=last_proj_crs,
                    area_sq_meters=round(total_area, 4) if has_area else None,
                    area_hectares=round(total_area / 10_000.0, 6) if has_area else None,
                    length_meters=round(total_len, 4) if has_len else None,
                    length_kilometers=round(total_len / 1000.0, 6) if has_len else None,
                    notes="Calculated composite measurements across GeometryCollection elements.",
                )
            except Exception as exc:
                logger.warning("Error measuring GeometryCollection: %s", exc)
                return MeasurementDetail(
                    geometry_type=geom_type,
                    supported=False,
                    notes=f"Could not calculate measurement for GeometryCollection: {str(exc)}",
                )

        # Default for any unknown geometry type
        return MeasurementDetail(
            geometry_type=geom_type,
            supported=False,
            notes=f"Geometry type '{geom_type}' is not supported for measurement calculations.",
        )
