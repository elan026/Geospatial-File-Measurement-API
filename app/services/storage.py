"""Thread-safe storage manager for uploaded geospatial files and processed measurements."""
import os
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import FileNotFoundException
from app.models.schemas import (
    FeatureItem,
    FileInfoResponse,
    FileMeasurementsResponse,
    MeasurementSummary,
)


class StoredFileRecord:
    def __init__(
        self,
        file_id: str,
        filename: str,
        stored_path: Path,
        crs: str,
        feature_count: int,
        geometry_types: list[str],
        status: str = "COMPLETED",
        summary: MeasurementSummary | None = None,
        features: list[FeatureItem] | None = None,
    ):
        self.file_id = file_id
        self.filename = filename
        self.stored_path = stored_path
        self.crs = crs
        self.feature_count = feature_count
        self.geometry_types = geometry_types
        self.status = status
        self.upload_time = datetime.now(timezone.utc)
        self.summary = summary or MeasurementSummary(
            total_features=feature_count,
            supported_features_count=0,
            unsupported_features_count=feature_count,
            total_area_sq_meters=0.0,
            total_area_hectares=0.0,
            total_length_meters=0.0,
            total_length_kilometers=0.0,
        )
        self.features = features or []


class StorageService:
    """Singleton service for file persistence and metadata lookup."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._records: dict[str, StoredFileRecord] = {}
                cls._instance._rw_lock = threading.RLock()
                settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            return cls._instance

    def generate_id(self) -> str:
        """Generate a clean, collision-free short identifier."""
        return uuid.uuid4().hex[:10]

    def save_upload(self, filename: str, content: bytes) -> tuple[str, Path]:
        """Save raw uploaded bytes to the storage directory."""
        file_id = self.generate_id()
        file_dir = settings.UPLOAD_DIR / file_id
        file_dir.mkdir(parents=True, exist_ok=True)

        target_path = file_dir / filename
        with open(target_path, "wb") as f:
            f.write(content)

        return file_id, target_path

    def register_dataset(
        self,
        file_id: str,
        filename: str,
        stored_path: Path,
        crs: str,
        features: list[FeatureItem],
        summary: MeasurementSummary,
    ) -> StoredFileRecord:
        """Register the processed dataset and measurement results."""
        geom_types = sorted(list({f.geometry_type for f in features}))
        record = StoredFileRecord(
            file_id=file_id,
            filename=filename,
            stored_path=stored_path,
            crs=crs,
            feature_count=len(features),
            geometry_types=geom_types,
            status="COMPLETED",
            summary=summary,
            features=features,
        )

        with self._rw_lock:
            self._records[file_id] = record

        return record

    def get_file_info(self, file_id: str) -> FileInfoResponse:
        """Retrieve file metadata summary."""
        with self._rw_lock:
            record = self._records.get(file_id)
            if not record:
                raise FileNotFoundException(file_id)

            return FileInfoResponse(
                id=record.file_id,
                filename=record.filename,
                feature_count=record.feature_count,
                crs=record.crs,
                status=record.status,
                upload_time=record.upload_time,
                geometry_types=record.geometry_types,
            )

    def get_measurements(self, file_id: str) -> FileMeasurementsResponse:
        """Retrieve measurements for all features in the file."""
        with self._rw_lock:
            record = self._records.get(file_id)
            if not record:
                raise FileNotFoundException(file_id)

            return FileMeasurementsResponse(
                file_id=record.file_id,
                filename=record.filename,
                original_crs=record.crs,
                summary=record.summary,
                features=record.features,
            )

    def list_files(self) -> list[FileInfoResponse]:
        """List all processed files."""
        with self._rw_lock:
            return [
                FileInfoResponse(
                    id=rec.file_id,
                    filename=rec.filename,
                    feature_count=rec.feature_count,
                    crs=rec.crs,
                    status=rec.status,
                    upload_time=rec.upload_time,
                    geometry_types=rec.geometry_types,
                )
                for rec in self._records.values()
            ]

    def delete_file(self, file_id: str) -> bool:
        """Delete file and its associated measurements."""
        with self._rw_lock:
            record = self._records.pop(file_id, None)
            if not record:
                raise FileNotFoundException(file_id)

            # Clean directory from disk
            parent_dir = record.stored_path.parent
            if parent_dir.exists():
                shutil.rmtree(parent_dir, ignore_errors=True)

            return True

    def clear(self) -> None:
        """Utility for test suite resets."""
        with self._rw_lock:
            self._records.clear()
            if settings.UPLOAD_DIR.exists():
                shutil.rmtree(settings.UPLOAD_DIR, ignore_errors=True)
                settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


storage_service = StorageService()
