"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


def create_app() -> FastAPI:
    """Create the Stage 1 API application."""
    app = FastAPI(title="Urban Emergency Simulation", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return process health."""
        return {"status": "ok"}

    return app


app = create_app()
