"""Pytest configuration and shared test fixtures."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.storage import storage_service

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


@pytest.fixture(autouse=True)
def clean_storage():
    """Clear in-memory and disk test storage before and after each test."""
    storage_service.clear()
    yield
    storage_service.clear()


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_kml_polygons_path():
    return SAMPLES_DIR / "polygons_sample.kml"


@pytest.fixture
def sample_kml_lines_path():
    return SAMPLES_DIR / "linestrings_sample.kml"


@pytest.fixture
def sample_kml_mixed_path():
    return SAMPLES_DIR / "mixed_sample.kml"


@pytest.fixture
def sample_shp_parcels_zip_path():
    return SAMPLES_DIR / "sample_parcels_shapefile.zip"


@pytest.fixture
def sample_shp_roads_zip_path():
    return SAMPLES_DIR / "sample_roads_shapefile.zip"
