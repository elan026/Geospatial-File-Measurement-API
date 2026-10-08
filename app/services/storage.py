"""Thread-safe storage manager for uploaded geospatial files and measurements."""
import shutil
import threading
import uuid
from pathlib import Path

from app.config import settings
from app.core.exceptions import FileNotFoundException
from app.models.schemas import FeatureItem, FileInfoResponse, FileMeasurementsResponse


class StoredFileRecord:
    def __init__(
        self,
        file_id: str,
        filename: str,
        stored_path: Path,
        crs: str,
        feature_count: int,
        features: list[FeatureItem],
        status: str = "COMPLETED",
    ):
        self.file_id = file_id
        self.filename = filename
        self.stored_path = stored_path
        self.crs = crs
        self.feature_count = feature_count
        self.features = features
        self.status = status


class StorageService:
    """Storage service for file persistence and retrieval."""

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
        """Generate short unique identifier."""
        return uuid.uuid4().hex[:8]

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
    ) -> StoredFileRecord:
        """Store the processed features."""
        record = StoredFileRecord(
            file_id=file_id,
            filename=filename,
            stored_path=stored_path,
            crs=crs,
            feature_count=len(features),
            features=features,
            status="COMPLETED",
        )

        with self._rw_lock:
            self._records[file_id] = record

        return record

    def get_file_info(self, file_id: str) -> FileInfoResponse:
        """Retrieve file information."""
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
            )

    def get_measurements(self, file_id: str) -> FileMeasurementsResponse:
        """Retrieve measurements for all features in the file."""
        with self._rw_lock:
            record = self._records.get(file_id)
            if not record:
                raise FileNotFoundException(file_id)

            return FileMeasurementsResponse(
                id=record.file_id,
                filename=record.filename,
                crs=record.crs,
                features=record.features,
            )

    def clear(self) -> None:
        """Reset storage (for test runs)."""
        with self._rw_lock:
            self._records.clear()
            if settings.UPLOAD_DIR.exists():
                shutil.rmtree(settings.UPLOAD_DIR, ignore_errors=True)
                settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


storage_service = StorageService()
