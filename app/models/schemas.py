"""Pydantic schemas for request validation and response serialization."""
from typing import Any
from pydantic import BaseModel, Field


class Measurement(BaseModel):
    """Calculated measurement for a supported geometry."""

    area: float | None = Field(None, description="Calculated area for Polygon")
    length: float | None = Field(None, description="Calculated length for LineString")


class FeatureItem(BaseModel):
    """Extracted geospatial feature."""

    feature_id: int | str = Field(..., description="Feature ID or index")
    geometry_type: str = Field(..., description="Geometry type")
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry")
    crs: str = Field(..., description="Coordinate Reference System")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Feature attributes and properties"
    )
    measurement: Measurement | None = Field(
        None, description="Measurement (Area for Polygon, Length for LineString, None for Point/unsupported)"
    )


class FileInfoResponse(BaseModel):
    """Information about the uploaded file."""

    id: str
    filename: str
    feature_count: int
    crs: str
    status: str


class FileMeasurementsResponse(BaseModel):
    """Measurements for the features in the file."""

    id: str
    filename: str
    crs: str
    features: list[FeatureItem]
