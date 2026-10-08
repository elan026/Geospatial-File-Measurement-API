# Geospatial File Measurement API

A FastAPI backend service that accepts a geospatial file (Zipped Shapefile or KML), processes the features within it, transforms geographic coordinates to appropriate projected coordinate systems, and returns spatial measurements.

**GitHub Repository**: [https://github.com/elan026/Geospatial-File-Measurement-API](https://github.com/elan026/Geospatial-File-Measurement-API)

---

## Setup

### Prerequisites
- Python 3.10+
- `pip`

### Run Locally

1. **Clone the repository**:
   ```bash
   git clone https://github.com/elan026/Geospatial-File-Measurement-API.git
   cd Geospatial-File-Measurement-API
   ```

2. **Create and activate a virtual environment**:
   ```bash
   # Windows PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the API server**:
   ```bash
   uvicorn app.main:app --reload
   ```
   The service will run at `http://127.0.0.1:8000`.  
   Interactive API docs are available at `http://127.0.0.1:8000/docs`.

### Run Tests
```bash
pytest -v
```

---

## API

The service provides three core endpoints under `/api/files/`:

### 1. Upload File
- **Method**: `POST`
- **Path**: `/api/files/`
- **Description**: Uploads and processes a `.zip` containing an ESRI Shapefile or a `.kml` file.
- **Request**: `multipart/form-data` with form field `file`.

**cURL Example**:
```bash
curl -X POST "http://127.0.0.1:8000/api/files/" -F "file=@sample.kml"
```

**Response Example (`201 Created`)**:
```json
{
  "id": "a1b2c3d4",
  "filename": "survey.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 2. File Information
- **Method**: `GET`
- **Path**: `/api/files/{id}/`
- **Description**: Returns metadata about an uploaded file.

**cURL Example**:
```bash
curl -X GET "http://127.0.0.1:8000/api/files/a1b2c3d4/"
```

**Response Example (`200 OK`)**:
```json
{
  "id": "a1b2c3d4",
  "filename": "survey.kml",
  "feature_count": 2,
  "crs": "EPSG:4326",
  "status": "COMPLETED"
}
```

---

### 3. Measurements
- **Method**: `GET`
- **Path**: `/api/files/{id}/measurements/`
- **Description**: Returns spatial measurements for the features in the file.
  - **Polygon**: Area calculated in square meters.
  - **LineString**: Length calculated in meters.
  - **Point**: No measurement (`null`).

**cURL Example**:
```bash
curl -X GET "http://127.0.0.1:8000/api/files/a1b2c3d4/measurements/"
```

**Response Example (`200 OK`)**:
```json
{
  "id": "a1b2c3d4",
  "filename": "survey.kml",
  "crs": "EPSG:4326",
  "features": [
    {
      "feature_id": "Zone Alpha",
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [
          [
            [-73.9712, 40.7831],
            [-73.9818, 40.7681],
            [-73.958, 40.7648],
            [-73.9495, 40.7798],
            [-73.9712, 40.7831]
          ]
        ]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Zone Alpha"
      },
      "measurement": {
        "area": 361502.45,
        "length": null
      }
    },
    {
      "feature_id": "Transit Line 1",
      "geometry_type": "LineString",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-73.9851, 40.7484],
          [-73.976, 40.77]
        ]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Transit Line 1"
      },
      "measurement": {
        "area": null,
        "length": 2541.12
      }
    },
    {
      "feature_id": "Survey Marker",
      "geometry_type": "Point",
      "geometry": {
        "type": "Point",
        "coordinates": [-73.98, 40.75]
      },
      "crs": "EPSG:4326",
      "properties": {
        "name": "Survey Marker"
      },
      "measurement": null
    }
  ]
}
```

---

## Architecture

### Application Structure
```
app/
├── main.py                # FastAPI entry point & router registration
├── config.py              # Application settings (upload limits, supported formats)
├── api/
│   ├── deps.py            # Dependency injection
│   └── routes/
│       └── files.py       # Upload, File Info, and Measurements endpoints
├── core/
│   ├── exceptions.py      # Custom exceptions and exception handlers
│   └── logging.py         # Logger setup
├── models/
│   └── schemas.py         # Pydantic response models
└── services/
    ├── storage.py         # File saving and metadata storage
    ├── crs_service.py     # CRS detection and dynamic UTM projection
    ├── measurement.py     # Area and length calculation logic
    └── parsers/
        ├── base.py        # Base parser interface
        ├── shapefile.py   # ZIP extraction and Shapefile reader
        └── kml.py         # KML reader (pyogrio with XML fallback)
```

### File-Processing Flow
1. Client uploads `.zip` or `.kml` via `POST /api/files/`.
2. The format is validated against allowed extensions.
3. For `.zip` Shapefiles: safely extracted and read using `pyogrio`.
4. For `.kml` files: parsed via `pyogrio` (with fallback XML parsing using `defusedxml`).
5. Extracts feature ID, geometry type, GeoJSON geometry, native CRS, and properties.

### Measurement Calculation Flow
1. For each feature, geometry type is evaluated:
   - **Polygon / MultiPolygon**: Transformed to a projected metric CRS $\to$ `area` computed in square meters.
   - **LineString / MultiLineString**: Transformed to a projected metric CRS $\to$ `length` computed in meters.
   - **Point**: Measurement is skipped (`null`).
   - **Other/Unsupported**: Gracefully handled without throwing an error (`null`).
2. Results are mapped and cached in storage for subsequent queries.

### CRS Handling
- Geospatial files frequently use geographic coordinate reference systems (such as `EPSG:4326`) where coordinates are in degrees of latitude/longitude.
- Calculating distance or area directly using degree coordinates leads to inaccurate results.
- **Strategy**:
  1. Inspect the source CRS (`is_geographic`).
  2. If geographic, determine the feature centroid $(\text{lon}, \text{lat})$.
  3. Calculate the local **Universal Transverse Mercator (UTM)** zone:
     $$\text{Zone} = \lfloor(\text{lon} + 180) / 6\rfloor + 1$$
     EPSG code is `32600 + Zone` for Northern hemisphere or `32700 + Zone` for Southern hemisphere (or Universal Polar Stereographic for polar regions).
  4. Reproject the geometry to this metric projected system using `pyproj.Transformer` before calculating area or length.
  5. If already in a projected planar system, the existing coordinates are used directly.

---

## Design Decisions

1. **FastAPI**: Selected for minimal overhead, fast ASGI performance, built-in validation, and automatic OpenAPI schema generation.
2. **Pyogrio and Shapely**: Chosen over calling GDAL binaries directly. Pyogrio reads vector datasets directly into memory, and Shapely 2.0 provides C-level GEOS routines for fast reprojection and measurement.
3. **Dual KML Parsing**: Pyogrio handles standard KML datasets rapidly. A fallback XML parser was implemented with `defusedxml` to ensure custom KML files (e.g. from Google Earth with unusual nesting) do not crash the service.
4. **Local UTM Auto-Selection**: Rather than forcing a single global projection (which introduces severe distortion away from its origin), the service dynamically chooses the local UTM zone based on each geometry's coordinates, ensuring accurate metric measurements.

---

## Learning and Future Scope

### Learnings
- Managing geographic coordinate distortion emphasized the necessity of projecting coordinates to local planar systems before measurement.
- Real-world geospatial files (especially KML) often deviate from standard schemas; defensive parsing and fallback strategies prevent service downtime.

### Future Scope
- **Asynchronous Task Queue**: Use Celery or Redis queue for background processing of multi-gigabyte shapefiles.
- **Persistent Spatial Database**: Store features in PostgreSQL with PostGIS for spatial queries and bounding-box indexing.
- **Additional Formats**: Add ingestion support for GeoJSON, GeoPackage (`.gpkg`), and FlatGeobuf.
