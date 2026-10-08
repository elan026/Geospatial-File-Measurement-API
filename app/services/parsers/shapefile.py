"""Shapefile ZIP parser supporting ESRI Shapefile component verification and extraction."""
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any
import math
import pandas as pd
import pyogrio

from app.core.exceptions import InvalidFileFormatException, FileProcessingException
from app.core.logging import logger
from app.services.crs_service import CRSService
from app.services.parsers.base import BaseGeoParser, ParsedGeoDataset, RawFeature


def sanitize_attributes(props: dict[str, Any]) -> dict[str, Any]:
    """Clean pandas / numpy types into standard JSON-serializable Python types."""
    cleaned = {}
    for k, v in props.items():
        if pd.isna(v) or v is None:
            cleaned[k] = None
        elif isinstance(v, (int, bool, str)):
            cleaned[k] = v
        elif isinstance(v, float):
            cleaned[k] = None if math.isnan(v) or math.isinf(v) else v
        elif hasattr(v, "item"):  # numpy scalars
            val = v.item()
            cleaned[k] = None if isinstance(val, float) and (math.isnan(val) or math.isinf(val)) else val
        elif hasattr(v, "isoformat"):  # datetime / date
            cleaned[k] = v.isoformat()
        else:
            cleaned[k] = str(v)
    return cleaned


class ShapefileParser(BaseGeoParser):
    """Parses zipped ESRI Shapefiles into geospatial datasets."""

    def parse(self, file_path: Path, original_filename: str) -> ParsedGeoDataset:
        extract_dir = Path(tempfile.mkdtemp(prefix="shp_extract_"))
        try:
            self._safe_extract_zip(file_path, extract_dir)
            shp_file = self._find_shapefile(extract_dir)

            # Check for essential companions
            base_stem = shp_file.stem
            parent = shp_file.parent
            shx_file = parent / f"{base_stem}.shx"
            dbf_file = parent / f"{base_stem}.dbf"

            if not shx_file.exists() and not (parent / f"{base_stem}.SHX").exists():
                logger.warning("Shapefile missing .shx index file: %s", shp_file.name)
            if not dbf_file.exists() and not (parent / f"{base_stem}.DBF").exists():
                logger.warning("Shapefile missing .dbf attributes file: %s", shp_file.name)

            # Read dataset using pyogrio
            try:
                gdf = pyogrio.read_dataframe(str(shp_file))
            except Exception as exc:
                raise FileProcessingException(f"Failed to read Shapefile: {str(exc)}")

            if gdf.empty:
                logger.info("Shapefile contains 0 features: %s", shp_file.name)

            # Determine CRS
            crs_str = "EPSG:4326"
            if gdf.crs is not None:
                crs_str = CRSService.normalize_crs_string(gdf.crs)
            else:
                logger.warning("Shapefile has no CRS (.prj missing). Defaulting to EPSG:4326")

            # Extract features
            features: list[RawFeature] = []
            for idx, row in gdf.iterrows():
                geom = row.get("geometry")
                if geom is None:
                    continue

                # Attributes excluding geometry
                props = row.drop(labels=["geometry"], errors="ignore").to_dict()
                cleaned_props = sanitize_attributes(props)

                feature_id = row.get("FID") or row.get("id") or idx
                features.append(
                    RawFeature(
                        feature_id=str(feature_id),
                        geometry=geom,
                        properties=cleaned_props,
                    )
                )

            return ParsedGeoDataset(
                features=features,
                crs=crs_str,
                file_type="Shapefile (.zip)",
                filename=original_filename,
            )

        finally:
            # Clean up extracted temp directory
            shutil.rmtree(extract_dir, ignore_errors=True)

    def _safe_extract_zip(self, zip_path: Path, target_dir: Path) -> None:
        """Extract zip archive with Zip Slip protection."""
        try:
            with zipfile.ZipFile(zip_path, "r") as archive:
                target_dir_resolved = target_dir.resolve()
                for member in archive.infolist():
                    member_path = (target_dir / member.filename).resolve()
                    if not str(member_path).startswith(str(target_dir_resolved)):
                        raise InvalidFileFormatException(
                            f"Suspicious zip entry attempted path traversal: {member.filename}"
                        )
                archive.extractall(target_dir)
        except zipfile.BadZipFile:
            raise InvalidFileFormatException("Provided file is not a valid zip archive.")

    def _find_shapefile(self, extract_dir: Path) -> Path:
        """Search extracted directory for .shp file."""
        shp_candidates = list(extract_dir.rglob("*.shp")) + list(extract_dir.rglob("*.SHP"))
        if not shp_candidates:
            raise InvalidFileFormatException(
                "Zip archive does not contain any .shp file. Please include .shp, .shx, and .dbf files."
            )
        # Select first matching shp (or one that matches directory name if possible)
        return shp_candidates[0]
