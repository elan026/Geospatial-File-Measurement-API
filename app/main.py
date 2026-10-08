"""FastAPI Application Entry Point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import files_router, health_router
from app.config import settings
from app.core.exceptions import GeospatialAPIException, geospatial_exception_handler
from app.core.logging import logger

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for web-based GIS frontends and dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain Exception Handlers
app.add_exception_handler(GeospatialAPIException, geospatial_exception_handler)

# Register API Routers
app.include_router(files_router, prefix=settings.API_PREFIX)
app.include_router(health_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    """Root entrypoint with interactive documentation links and metadata."""
    return JSONResponse(
        content={
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
            "documentation": "/docs",
            "alternative_docs": "/redoc",
            "endpoints": {
                "upload_file": f"{settings.API_PREFIX}/files/",
                "file_info": f"{settings.API_PREFIX}/files/{{id}}/",
                "file_measurements": f"{settings.API_PREFIX}/files/{{id}}/measurements/",
                "health_check": f"{settings.API_PREFIX}/health",
            },
        }
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting %s v%s server...", settings.APP_NAME, settings.APP_VERSION)
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
