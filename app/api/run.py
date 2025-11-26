"""
Entry point for running PATAS API server.

Usage:
    # Development
    patas-api
    # or
    python -m app.api.run
    
    # Production
    ENVIRONMENT=production patas-api
    
Environment Variables:
    API_HOST: Host to bind to (default: 0.0.0.0)
    API_PORT: Port to listen on (default: 8000)
    API_RELOAD: Enable auto-reload (default: false)
    API_MAX_REQUEST_SIZE: Maximum request body size in bytes (default: 10MB)
"""
import uvicorn
from app.config import settings


def main():
    """Main entry point for PATAS API server."""
    # Configure uvicorn options
    config = {
        "app": "app.api.main:app",
        "host": settings.api_host,
        "port": settings.api_port,
        "reload": settings.api_reload,
        # Limit concurrency to prevent resource exhaustion
        "limit_concurrency": 1000,
        # Timeout for keepalive connections
        "timeout_keep_alive": 30,
    }
    
    # Production-specific settings
    if settings.is_production():
        config.update({
            "reload": False,  # Never reload in production
            "access_log": False,  # Disable access log for performance (use structured logging instead)
            "log_level": "warning",  # Reduce uvicorn log noise
        })
    else:
        config.update({
            "log_level": "info",
        })
    
    uvicorn.run(**config)


if __name__ == "__main__":
    main()

