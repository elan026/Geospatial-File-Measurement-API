"""API endpoints for geospatial file upload, metadata lookup, and measurement retrieval."""
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
    FileUploadResponse,
    MeasurementSummary,
)
from app.services.measurement import MeasurementService
from app.services.parsers.kml import KMLParser
from app.services.parsers.shapefile import ShapefileParser
from app.services.storage import StorageService

router = APIRouter(prefix="/files", tags=["Files & Measurements"])

shapefile_parser = ShapefileParser()
kml_parser = KMLParser()


@router.post(
    "/",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a geospatial file",
    description="Accepts a zipped ESRI Shapefile (.zip) or a Keyhole Markup Language (.kml) file.",
)
async def upload_file(
    file: UploadFile = File(..., description="Geospatial file (.zip Shapefile or .kml)"),
    storage: StorageService = Depends(get_storage_service),
) -> FileUploadResponse:
    filename = file.filename or "unknown"
    suffix = Path(filename).suffix.lower()

    if suffix not in settings.ALLOWED_EXTENSIONS:
        raise InvalidFileFormatException(
            f"Unsupported file extension '{suffix}'. Allowed formats: {settings.ALLOWED_EXTENSIONS}",
            details={"filename": filename, "allowed": settings.ALLOWED_EXTENSIONS},
        )

    # Read content
    content = await file.read()
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise FileSizeExceededException(settings.MAX_FILE_SIZE_MB)

    if len(content) == 0:
        raise InvalidFileFormatException("Uploaded file is empty.")

    # Save to disk
    file_id, stored_path = storage.save_upload(filename, content)
    logger.info("Saved upload '%s' with ID %s (%d bytes)", filename, file_id, len(content))

    # Select parser
    if suffix == ".zip":
        parser = shapefile_parser
    elif suffix == ".kml":
        parser = kml_parser
    else:
        raise InvalidFileFormatException(f"No parser available for extension '{suffix}'")

    # Parse dataset
    try:
        parsed_dataset = parser.parse(stored_path, filename)
    except Exception as exc:
        logger.error("Processing failed for file %s: %s", file_id, exc)
        # Attempt to delete file on failure
        storage.delete_file(file_id)
        if isinstance(exc, (InvalidFileFormatException, FileProcessingException)):
            raise exc
        raise FileProcessingException(f"Error processing geospatial file: {str(exc)}")

    # Process measurements and structure features
    features: list[FeatureItem] = []
    total_area_m2 = 0.0
    total_length_m = 0.0
    supported_count = 0
    unsupported_count = 0

    for raw in parsed_dataset.features:
        measurement = MeasurementService.calculate_measurement(
            raw.geometry, parsed_dataset.crs
        )

        if measurement.supported:
            supported_count += 1
            if measurement.area_sq_meters is not None:
                total_area_m2 += measurement.area_sq_meters
            if measurement.length_meters is not None:
                total_length_m += measurement.length_meters
        else:
            unsupported_count += 1

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

    # Generate summary
    summary = MeasurementSummary(
        total_features=len(features),
        supported_features_count=supported_count,
        unsupported_features_count=unsupported_count,
        total_area_sq_meters=round(total_area_m2, 4),
        total_area_hectares=round(total_area_m2 / 10_000.0, 6),
        total_length_meters=round(total_length_m, 4),
        total_length_kilometers=round(total_length_m / 1000.0, 6),
    )

    # Store record
    record = storage.register_dataset(
        file_id=file_id,
        filename=filename,
        stored_path=stored_path,
        crs=parsed_dataset.crs,
        features=features,
        summary=summary,
    )

    return FileUploadResponse(
        id=record.file_id,
        filename=record.filename,
        feature_count=record.feature_count,
        crs=record.crs,
        status=record.status,
        message="File processed and measurements calculated successfully.",
        file_info_url=f"/api/files/{record.file_id}/",
        measurements_url=f"/api/files/{record.file_id}/measurements/",
    )


@router.get(
    "/{file_id}/",
    response_model=FileInfoResponse,
    summary="Get file information",
    description="Returns metadata about an uploaded geospatial file including feature count and CRS.",
)
async def get_file_info(
    file_id: str,
    storage: StorageService = Depends(get_storage_service),
) -> FileInfoResponse:
    return storage.get_file_info(file_id)


@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    summary="Get feature measurements",
    description="Returns calculated spatial measurements (area for polygons, length for lines) for all features.",
)
async def get_file_measurements(
    file_id: str,
    storage: StorageService = Depends(get_storage_service),
) -> FileMeasurementsResponse:
    return storage.get_measurements(file_id)


@router.get(
    "/",
    response_model=list[FileInfoResponse],
    summary="List all uploaded files",
    description="Returns metadata for all files processed during this session.",
)
async def list_files(
    storage: StorageService = Depends(get_storage_service),
) -> list[FileInfoResponse]:
    return storage.list_files()


@router.delete(
    "/{file_id}/",
    status_code=status.HTTP_200_OK,
    summary="Delete an uploaded file",
    description="Removes the file and all associated measurement records.",
)
async def delete_file(
    file_id: str,
    storage: StorageService = Depends(get_storage_service),
) -> dict[str, str]:
    storage.delete_file(file_id)
    return {"message": f"File '{file_id}' successfully deleted."}
