"""Domain exceptions and HTTP error handlers."""
from fastapi import Request
from fastapi.responses import JSONResponse


class GeospatialAPIException(Exception):
    """Base exception for all domain-specific errors."""

    def __init__(self, message: str, status_code: int = 400, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class FileNotFoundException(GeospatialAPIException):
    def __init__(self, file_id: str):
        super().__init__(
            message=f"File with ID '{file_id}' not found.",
            status_code=404,
            details={"file_id": file_id},
        )


class InvalidFileFormatException(GeospatialAPIException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, status_code=400, details=details)


class FileProcessingException(GeospatialAPIException):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message=message, status_code=422, details=details)


class FileSizeExceededException(GeospatialAPIException):
    def __init__(self, max_size_mb: int):
        super().__init__(
            message=f"File exceeds maximum allowed upload size of {max_size_mb} MB.",
            status_code=413,
            details={"max_size_mb": max_size_mb},
        )


async def geospatial_exception_handler(
    request: Request, exc: GeospatialAPIException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
            "path": request.url.path,
        },
    )
