"""Base interface and data classes for geospatial file parsers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from shapely.geometry.base import BaseGeometry


@dataclass
class RawFeature:
    """Represents an extracted feature prior to API response formatting."""
    feature_id: int | str
    geometry: BaseGeometry
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedGeoDataset:
    """Dataset extracted from an uploaded geospatial file."""
    features: list[RawFeature]
    crs: str
    file_type: str
    filename: str


class BaseGeoParser(ABC):
    """Abstract parser interface for geospatial formats."""

    @abstractmethod
    def parse(self, file_path: Path, original_filename: str) -> ParsedGeoDataset:
        """Parse the input file and extract features, CRS, and properties."""
        pass
