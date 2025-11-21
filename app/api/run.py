"""
Entry point for running PATAS API server.
"""
import uvicorn
from app.config import settings


def main():
    """Main entry point for PATAS API server."""
    uvicorn.run(
        "app.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


if __name__ == "__main__":
    main()

