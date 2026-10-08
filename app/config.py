"""Application configuration settings."""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Geospatial File Measurement API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Production-grade FastAPI service to upload, parse, and measure "
        "geospatial files (Shapefile .zip and KML) with automated CRS projection."
    )
    API_PREFIX: str = "/api"
    UPLOAD_DIR: Path = Path("uploads")
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".zip", ".kml"]
    DEFAULT_GEOGRAPHIC_CRS: str = "EPSG:4326"

    model_config = {
        "env_prefix": "GEO_API_",
        "case_sensitive": False,
    }


settings = Settings()
