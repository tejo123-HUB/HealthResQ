from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.comm.routes import router as comm_router
from backend.ops.router import router as ops_router


def create_app() -> FastAPI:
    app = FastAPI(title="HealthResQ API", version="0.1.0")

    # The Web Application (frontend/) runs as a separate Next.js dev server (Direction 4).
    # "localhost" and "127.0.0.1" are different origins to the browser even though they resolve
    # to the same machine — allow both, since either is a normal way to reach the dev server (and
    # a mismatch here fails every request silently from the frontend's point of view: the fetch
    # throws before a response is ever seen, which looks exactly like "login is failing").
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):3000",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ops_router)
    app.include_router(comm_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.get("/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
