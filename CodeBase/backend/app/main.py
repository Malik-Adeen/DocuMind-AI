from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.api.v1 import auth, documents, exports
from app.core.config import get_settings
from app.core.errors import install_error_handlers

logger = logging.getLogger("app")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    application = FastAPI(title="DocuMind", version="0.3.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(application)

    @application.middleware("http")
    async def trace(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        logger.info(
            "%s %s -> %s trace_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            trace_id,
        )
        return response

    application.include_router(auth.router)
    application.include_router(documents.router)
    application.include_router(exports.router)
    return application


app = create_app()
