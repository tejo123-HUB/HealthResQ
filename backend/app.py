from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.comm.routes import router as comm_router
from backend.db import engine
from backend.intelligence.api import router as intelligence_router
from backend.intelligence.graph.schema import ensure_graph_ready
from backend.ops.router import router as ops_router


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """INT-06: the AGE extension/graph must exist and every connection must run `LOAD 'age'`
    before any INT graph query can resolve `agtype` — without this, the app boots fine but every
    /intelligence/* call fails with "type agtype does not exist" the first time it touches a
    fresh connection."""
    ensure_graph_ready(engine)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="HealthResQ API", version="0.1.0", lifespan=_lifespan)

    # The Web Application (frontend/) runs as a separate Next.js dev server (Direction 4).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ops_router)
    app.include_router(intelligence_router)
    app.include_router(comm_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
