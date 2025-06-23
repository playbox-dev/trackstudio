"""
Main FastAPI Application for WebRTC Multi-Camera Streaming

This server provides WebRTC streaming and integrates with the vision package
for computer vision processing through well-defined APIs.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import vision_websocket
from .api import calibration, cameras, vision_control, webrtc
from .config import ServerConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    logger.info("Creating FastAPI application...")

    app = FastAPI(
        title="Multi-Camera WebRTC Streaming Server",
        version="1.0.0",
        description="WebRTC streaming server with computer vision integration",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ServerConfig.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(cameras.router, prefix="/api/cameras", tags=["cameras"])
    app.include_router(calibration.router, prefix="/api/calibration", tags=["calibration"])
    app.include_router(vision_control.router, prefix="/api/vision", tags=["vision-control"])
    app.include_router(webrtc.router, prefix="/ws", tags=["webrtc"])
    app.include_router(vision_websocket.router, prefix="/ws", tags=["vision-websocket"])

    # Serve static files (React frontend)
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists():
        # Mount static files for assets
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

        # Serve root static files (favicon.svg, favicon.ico, etc.)
        @app.get("/favicon.svg")
        @app.head("/favicon.svg")
        async def serve_favicon_svg():
            favicon_path = static_dir / "favicon.svg"
            if favicon_path.exists():
                return FileResponse(str(favicon_path), media_type="image/svg+xml")
            return {"error": "Favicon not found"}, 404

        @app.get("/favicon.ico")
        @app.head("/favicon.ico")
        async def serve_favicon_ico():
            # Redirect .ico requests to .svg since we only have SVG
            favicon_path = static_dir / "favicon.svg"
            if favicon_path.exists():
                return FileResponse(str(favicon_path), media_type="image/svg+xml")
            return {"error": "Favicon not found"}, 404

        # Serve index.html for all non-API routes (React Router support)
        @app.get("/{full_path:path}")
        async def serve_react_app(full_path: str):
            # Skip API, WebSocket routes, and static files
            if full_path.startswith(("api/", "ws/", "assets/")) or full_path in ["favicon.svg", "favicon.ico"]:
                return {"error": "Not found"}, 404

            # Serve index.html for all other routes
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {
                "error": "Frontend not built",
                "message": "Please build the React frontend first",
                "instructions": "Run 'npm run build' in the web/ directory",
            }
    else:
        logger.warning(f"Static directory not found at {static_dir}")

    # Root endpoint - now handled by React app above
    # Keeping API info endpoint
    @app.get("/api/info")
    async def api_info():
        return {
            "message": "Multi-Camera WebRTC Streaming Server",
            "version": "1.0.0",
            "architecture": {
                "server": "FastAPI + WebRTC (this package)",
                "vision": "Computer vision processing (separate package)",
                "frontend": "React + TypeScript (web/)",
            },
            "config": {
                "port": ServerConfig.SERVER_PORT,
                "vision_integration": ServerConfig.VISION_API_ENABLED,
                "cameras": len(ServerConfig.get_enabled_streams()),
            },
        }

    # Health check
    @app.get("/api/health")
    async def health():
        # Check vision package availability
        vision_status = "unknown"
        try:
            import importlib.util  # noqa: PLC0415

            if importlib.util.find_spec("vision") is not None:
                vision_status = "available"
        except ImportError:
            vision_status = "not_available"

        return {
            "status": "healthy",
            "server": {
                "port": ServerConfig.SERVER_PORT,
            },
            "vision": {"status": vision_status, "integration_enabled": ServerConfig.VISION_API_ENABLED},
            "cameras": {
                "total": len(ServerConfig.DEFAULT_CAMERAS),
                "enabled": len([c for c in ServerConfig.DEFAULT_CAMERAS if c.get("enabled", True)]),
            },
        }

    logger.info("FastAPI application created successfully")
    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting server on {ServerConfig.SERVER_NAME}:{ServerConfig.SERVER_PORT}")
    uvicorn.run(
        app,
        host=ServerConfig.SERVER_NAME,
        port=ServerConfig.SERVER_PORT,
        reload=ServerConfig.SERVER_RELOAD,
        log_level="info",
    )
