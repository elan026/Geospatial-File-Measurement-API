"""Pydantic schemas for request validation and response serialization."""
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class MeasurementDetail(BaseModel):
    """Detailed measurement calculations for a specific geometry."""

    geometry_type: str = Field(..., description="Type of geometry, e.g. Polygon, LineString")
    supported: bool = Field(..., description="Whether this geometry type supports spatial measurement")
    projected_crs: str | None = Field(
        None, description="Projected Coordinate Reference System used for metric measurement"
    )
    # Area measurements (Polygon / MultiPolygon)
    area_sq_meters: float | None = Field(
        None, description="Area in square meters (m²)"
    )
    area_hectares: float | None = Field(
        None, description="Area in hectares (ha)"
    )
    area_acres: float | None = Field(
        None, description="Area in acres"
    )
    perimeter_meters: float | None = Field(
        None, description="Perimeter in meters (m)"
    )
    # Length measurements (LineString / MultiLineString)
    length_meters: float | None = Field(
        None, description="Total length in meters (m)"
    )
    length_kilometers: float | None = Field(
        None, description="Total length in kilometers (km)"
    )
    notes: str | None = Field(
        None, description="Informational notes or reasons if measurement is not applicable"
    )


class FeatureItem(BaseModel):
    """Extracted geospatial feature item."""

    feature_id: int | str = Field(..., description="Unique index or ID of the feature")
    geometry_type: str = Field(..., description="GeoJSON geometry type")
    geometry: dict[str, Any] = Field(..., description="GeoJSON geometry representation")
    crs: str = Field(..., description="Coordinate Reference System of the feature")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Attributes / properties associated with the feature"
    )
    measurement: MeasurementDetail | None = Field(
        None, description="Spatial measurement calculated for the feature"
    )


class FileInfoResponse(BaseModel):
    """Basic metadata about the uploaded file."""

    id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original uploaded filename")
    feature_count: int = Field(..., description="Total number of geospatial features")
    crs: str = Field(..., description="Original/Detected Coordinate Reference System")
    status: str = Field(..., description="Processing status (e.g. COMPLETED, FAILED)")
    upload_time: datetime | None = Field(
        None, description="Timestamp when file was uploaded"
    )
    geometry_types: list[str] = Field(
        default_factory=list, description="List of unique geometry types found in the file"
    )


class MeasurementSummary(BaseModel):
    """Aggregated measurements for the entire file."""

    total_features: int = Field(..., description="Total features processed")
    supported_features_count: int = Field(..., description="Features with supported measurements")
    unsupported_features_count: int = Field(..., description="Features without measurements (e.g. Points)")
    total_area_sq_meters: float = Field(0.0, description="Sum of all polygon areas in m²")
    total_area_hectares: float = Field(0.0, description="Sum of all polygon areas in hectares")
    total_length_meters: float = Field(0.0, description="Sum of all line lengths in meters")
    total_length_kilometers: float = Field(0.0, description="Sum of all line lengths in kilometers")


class FileMeasurementsResponse(BaseModel):
    """Full measurements response for all features in the file."""

    file_id: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    original_crs: str = Field(..., description="Source Coordinate Reference System")
    summary: MeasurementSummary = Field(..., description="High-level measurement summary")
    features: list[FeatureItem] = Field(..., description="List of individual features and measurements")


class FileUploadResponse(BaseModel):
    """Response returned immediately after file upload and processing."""

    id: str
    filename: str
    feature_count: int
    crs: str
    status: str
    message: str
    file_info_url: str
    measurements_url: str


class HealthResponse(BaseModel):
    """API health status schema."""

    status: str
    app_name: str
    version: str
    timestamp: datetime
