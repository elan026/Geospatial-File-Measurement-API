"""Integration tests for FastAPI endpoints: upload, info, measurements."""
import io
import pytest


def test_health_check(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "/docs" in data["documentation"]


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
    assert upload_data["feature_count"] == 2
    assert upload_data["crs"] == "EPSG:4326"
    assert upload_data["status"] == "COMPLETED"

    # 2. Get File Info - Verify exact specification structure
    info_res = client.get(f"/api/files/{file_id}/")
    assert info_res.status_code == 200
    info_data = info_res.json()
    assert info_data["id"] == file_id
    assert info_data["filename"] == "polygons_sample.kml"
    assert info_data["feature_count"] == 2
    assert info_data["crs"] == "EPSG:4326"
    assert info_data["status"] == "COMPLETED"

    # 3. Get Measurements
    measure_res = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_res.status_code == 200
    measure_data = measure_res.json()
    assert measure_data["file_id"] == file_id
    assert measure_data["summary"]["total_features"] == 2
    assert measure_data["summary"]["supported_features_count"] == 2
    assert measure_data["summary"]["total_area_sq_meters"] > 0
    assert len(measure_data["features"]) == 2

    # Check first feature details
    first_feat = measure_data["features"][0]
    assert first_feat["geometry_type"] == "Polygon"
    assert first_feat["measurement"]["supported"] is True
    assert first_feat["measurement"]["area_sq_meters"] > 0
    assert first_feat["measurement"]["perimeter_meters"] > 0
    assert first_feat["measurement"]["projected_crs"] == "EPSG:32618"  # NYC UTM Zone 18N


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
    assert measure_data["summary"]["total_features"] == 2
    assert measure_data["summary"]["total_area_sq_meters"] > 0


def test_upload_mixed_geometries_kml(client, sample_kml_mixed_path):
    with open(sample_kml_mixed_path, "rb") as f:
        mixed_bytes = f.read()

    upload_res = client.post(
        "/api/files/",
        files={"file": ("mixed_sample.kml", mixed_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert upload_res.status_code == 201
    file_id = upload_data = upload_res.json()["id"]

    measure_res = client.get(f"/api/files/{file_id}/measurements/")
    assert measure_res.status_code == 200
    measure_data = measure_res.json()
    
    # In mixed: Point (unsupported measurement), Line (supported length), Polygon (supported area)
    features = measure_data["features"]
    point_feat = next(f for f in features if f["geometry_type"] == "Point")
    line_feat = next(f for f in features if f["geometry_type"] == "LineString")
    poly_feat = next(f for f in features if f["geometry_type"] == "Polygon")

    # Point: graceful handling
    assert point_feat["measurement"]["supported"] is False
    assert point_feat["measurement"]["area_sq_meters"] is None
    assert point_feat["measurement"]["length_meters"] is None

    # Line: length measurement
    assert line_feat["measurement"]["supported"] is True
    assert line_feat["measurement"]["length_meters"] > 0

    # Polygon: area measurement
    assert poly_feat["measurement"]["supported"] is True
    assert poly_feat["measurement"]["area_sq_meters"] > 0


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
    assert "Unsupported file extension" in data["message"]


def test_upload_empty_file(client):
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "InvalidFileFormatException"
    assert "empty" in data["message"].lower()


def test_list_and_delete_file(client, sample_kml_polygons_path):
    with open(sample_kml_polygons_path, "rb") as f:
        file_bytes = f.read()

    upload_res = client.post(
        "/api/files/",
        files={"file": ("test_delete.kml", file_bytes, "application/vnd.google-earth.kml+xml")},
    )
    file_id = upload_res.json()["id"]

    # Verify present in list
    list_res = client.get("/api/files/")
    assert list_res.status_code == 200
    file_ids = [item["id"] for item in list_res.json()]
    assert file_id in file_ids

    # Delete
    del_res = client.delete(f"/api/files/{file_id}/")
    assert del_res.status_code == 200

    # Verify 404 on subsequent get
    assert client.get(f"/api/files/{file_id}/").status_code == 404
