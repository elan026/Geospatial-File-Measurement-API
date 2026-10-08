"""Integration tests for FastAPI endpoints: upload, info, measurements."""
import pytest


def test_upload_kml_polygons_and_retrieve_measurements(client, sample_kml_polygons_path):
    with open(sample_kml_polygons_path, "rb") as f:
        file_bytes = f.read()

    # 1. Upload KML
    upload_res = client.post(
        "/api/files/",
        files={"file": ("polygons_sample.kml", file_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    file_id = upload_data["id"]
    assert upload_data == {
        "id": file_id,
        "filename": "polygons_sample.kml",
        "feature_count": 2,
        "crs": "EPSG:4326",
        "status": "COMPLETED",
    }

    # 2. Get File Info - Verify exact specification structure
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    assert info_res.json() == {
        "id": file_id,
        "filename": "polygons_sample.kml",
        "feature_count": 2,
        "crs": "EPSG:4326",
        "status": "COMPLETED",
    }

    # 3. Get Measurements
    measure_res = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_res.status_code == 200
    measure_data = measure_res.json()
    assert measure_data["id"] == file_id
    assert measure_data["filename"] == "polygons_sample.kml"
    assert measure_data["crs"] == "EPSG:4326"
    assert len(measure_data["features"]) == 2

    # Check first feature details
    first_feat = measure_data["features"][0]
    assert first_feat["geometry_type"] == "Polygon"
    assert first_feat["measurement"]["area"] > 0
    assert first_feat["measurement"]["length"] is None


def test_upload_shapefile_parcels(client, sample_shp_parcels_zip_path):
    with open(sample_shp_parcels_zip_path, "rb") as f:
        zip_bytes = f.read()

    upload_res = client.post(
        "/api/files/",
        files={"file": ("sample_parcels.zip", zip_bytes, "application/zip")},
    )
    assert upload_res.status_code == 201
    upload_data = upload_res.json()
    file_id = upload_data["id"]
    assert upload_data["feature_count"] == 2
    assert upload_data["status"] == "COMPLETED"

    measure_res = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_res.status_code == 200
    measure_data = measure_res.json()
    assert len(measure_data["features"]) == 2
    assert measure_data["features"][0]["measurement"]["area"] > 0


def test_upload_mixed_geometries_kml(client, sample_kml_mixed_path):
    with open(sample_kml_mixed_path, "rb") as f:
        mixed_bytes = f.read()

    upload_res = client.post(
        "/api/files/",
        files={"file": ("mixed_sample.kml", mixed_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    measure_res = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_res.status_code == 200
    measure_data = measure_res.json()
    
    features = measure_data["features"]
    point_feat = next(f for f in features if f["geometry_type"] == "Point")
    line_feat = next(f for f in features if f["geometry_type"] == "LineString")
    poly_feat = next(f for f in features if f["geometry_type"] == "Polygon")

    # Point: no measurement
    assert point_feat["measurement"] is None

    # Line: length measurement
    assert line_feat["measurement"]["length"] > 0
    assert line_feat["measurement"]["area"] is None

    # Polygon: area measurement
    assert poly_feat["measurement"]["area"] > 0
    assert poly_feat["measurement"]["length"] is None


def test_get_nonexistent_file_404(client):
    response = client.get("/api/files/nonexistent_id/")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "FileNotFoundException"


def test_upload_unsupported_file_extension(client):
    response = client.post(
        "/api/files/",
        files={"file": ("document.pdf", b"fake pdf content", "application/pdf")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "InvalidFileFormatException"


def test_upload_empty_file(client):
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "InvalidFileFormatException"
