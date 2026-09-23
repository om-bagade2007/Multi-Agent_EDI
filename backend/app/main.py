"""FastAPI application entry point."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import _pune_network, _settings, router


def create_app() -> FastAPI:
    """Create the Stage 1 API application."""
    app = FastAPI(title="Urban Emergency Simulation", version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Return process health."""
        if _settings.simulation_mode.lower() == "pune":
            try:
                network = _pune_network()
                return {"status": "ok", "mode": "pune", "nodes": str(network.graph.number_of_nodes()), "edges": str(network.graph.number_of_edges())}
            except HTTPException as error:
                return {"status": "error", "detail": str(getattr(error, "detail", error))}
        return {"status": "ok"}

    return app


app = create_app()
