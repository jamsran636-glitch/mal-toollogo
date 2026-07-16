import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    analytics,
    auth,
    backup,
    cattle,
    finance,
    herders,
    horses,
    images,
    reports,
    sheep,
    system,
)
from .config import get_settings


settings = get_settings()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("mal_tooollogo")

app = FastAPI(
    title=settings.app_name,
    version="2.0.0",
    description="Мал тооллого системийн API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Idempotency-Key",
        "If-Match",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id", "")[:64] or str(uuid.uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - started) * 1000,
        request_id,
    )
    return response


for router in (
    system.router,
    auth.router,
    horses.router,
    cattle.router,
    sheep.router,
    finance.router,
    herders.router,
    analytics.router,
    images.router,
    reports.router,
    backup.router,
):
    app.include_router(router)
