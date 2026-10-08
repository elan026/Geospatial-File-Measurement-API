"""API endpoints for geospatial file upload, metadata lookup, and measurements."""
from pathlib import Path
from fastapi import APIRouter, Depends, File, UploadFile, status
from shapely.geometry import mapping

from app.api.deps import get_storage_service
from app.config import settings
from app.core.exceptions import (
    InvalidFileFormatException,
    FileSizeExceededException,
    FileProcessingException,
)
from app.core.logging import logger
from app.models.schemas import (
    FeatureItem,
    FileInfoResponse,
    FileMeasurementsResponse,
)
from app.services.measurement import MeasurementService
from app.services.parsers.kml import KMLParser
from app.services.parsers.shapefile import ShapefileParser
from app.services.storage import StorageService

router = APIRouter(prefix="/files", tags=["Files"])

shapefile_parser = ShapefileParser()
kml_parser = KMLParser()


@router.post(
    "/",
    response_model=FileInfoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.zip Shapefile or .kml)"),
    storage: StorageService = Depends(get_storage_service),
) -> FileInfoResponse:
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()

    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise InvalidFileFormatException(
            f"Unsupported file format '{suffix}'. Allowed formats: {settings.ALLOWED_EXTENSIONS}"
        )

    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise FileSizeExceededException(settings.MAX_FILE_SIZE_MB)

    if len(content) == 0:
        raise InvalidFileFormatException("Uploaded file is empty.")

    file_id, stored_path = storage.save_upload(filename, content)

    # Select parser based on extension
    parser = shapefile_parser if suffix == ".zip" else kml_parser

    try:
        parsed_dataset = parser.parse(stored_path, filename)
    except Exception as exc:
        logger.error("Processing failed for file %s: %s", file_id, exc)
        if isinstance(exc, (InvalidFileFormatException, FileProcessingException)):
            raise exc
        raise FileProcessingException(f"Error processing geospatial file: {str(exc)}")

    # Extract features and calculate measurements
    features: list[FeatureItem] = []
    for raw in parsed_dataset.features:
        measurement = MeasurementService.calculate_measurement(
            raw.geometry, parsed_dataset.crs
        )
        geo_json_dict = mapping(raw.geometry)
        features.append(
            FeatureItem(
                feature_id=raw.feature_id,
                geometry_type=raw.geometry.geom_type,
                geometry=geo_json_dict,
                crs=parsed_dataset.crs,
                properties=raw.properties,
                measurement=measurement,
            )
        )

    # Store dataset
    record = storage.register_dataset(
        file_id=file_id,
        filename=filename,
        stored_path=stored_path,
        crs=parsed_dataset.crs,
        features=features,
    )

    return FileInfoResponse(
        id=record.file_id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
    )


@router.get(
    "/{id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
)
async def get_file_info(
    id: str,
    storage: StorageService = Depends(get_storage_service),
) -> FileInfoResponse:
    return storage.get_file_info(id)


@router.get(
    "/{id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get measurements for features in the file",
)
async def get_file_measurements(
    id: str,
    storage: StorageService = Depends(get_storage_service),
) -> FileMeasurementsResponse:
    return storage.get_measurements(id)
