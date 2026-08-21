from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.ops.router import router as ops_router


def create_app() -> FastAPI:
    app = FastAPI(title="HealthResQ API", version="0.1.0")
    app.include_router(ops_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
